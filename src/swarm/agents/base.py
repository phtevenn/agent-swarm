"""Base class for coding agent adapters."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

from swarm.config.schema import AgentConfig, AgentType, ApprovalMode

logger = logging.getLogger(__name__)


class WorkerNeedsFeedback(Exception):
    """Raised when a worker outputs <swarm:need-feedback> and requests lead input."""

    def __init__(self, question: str, agent_name: str = "") -> None:
        self.question = question
        self.agent_name = agent_name
        super().__init__(question)


class BaseAgent(ABC):
    """Common interface that all agent adapters must implement.

    Each adapter wraps a CLI tool (claude, codex, agent, etc.) and
    provides async methods the orchestrator can call.

    The approval_mode is inherited from the swarm-level config so that
    all agents (lead + workers) operate with the same permission level.
    """

    agent_type: AgentType

    def __init__(
        self,
        config: AgentConfig,
        work_dir: str = ".",
        approval_mode: ApprovalMode = ApprovalMode.DEFAULT,
    ) -> None:
        self.config = config
        self.work_dir = work_dir
        self.enabled = config.enabled
        self.approval_mode = approval_mode
        self._session_started = False

    @property
    def name(self) -> str:
        return self.config.agent.value

    @abstractmethod
    def _build_cmd(self) -> list[str]:
        """Build the base CLI command including approval-mode flags."""

    def build_execute_args(self, task: str, context: str = "") -> list[str]:
        """Build the full argv for executing a one-shot task (for streaming or execute).

        Default: base cmd + single prompt string. Override if the CLI needs
        a flag before the prompt (e.g. gemini -p "...").
        """
        prompt = f"{task}\n\n{context}" if context else task
        return [*self._build_cmd(), prompt]

    @abstractmethod
    async def send(
        self,
        message: str,
        system_prompt: str | None = None,
        continue_session: bool = False,
    ) -> str:
        """Send a conversational message and return the response.

        Used for lead-agent interaction. Supports session continuity
        via continue_session so the agent retains context.
        """

    @abstractmethod
    async def execute(self, task: str, context: str = "") -> str:
        """Execute a one-shot task and return the result.

        Used for worker agents receiving delegated subtasks.
        No session continuity — each call is independent.
        """

    async def execute_streaming(self, task: str, context: str = "") -> tuple[str, AsyncIterator[str]]:
        """Execute a task, yielding output lines as they arrive.

        Returns (final_result, line_iterator). Default falls back to
        non-streaming execute. Adapters can override for real streaming.
        """
        result = await self.execute(task, context)
        return result

    async def health_check(self) -> bool:
        """Verify the underlying CLI tool is reachable."""
        return True

    async def _run_cli(self, args: list[str], stdin: str | None = None) -> str:
        """Run a CLI command and return stdout."""
        logger.debug("Running: %s", " ".join(args))
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE if stdin else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.work_dir,
        )
        stdout, stderr = await proc.communicate(input=stdin.encode() if stdin else None)
        if proc.returncode != 0:
            err_msg = stderr.decode().strip()
            raise RuntimeError(f"{args[0]} exited with code {proc.returncode}: {err_msg}")
        return stdout.decode().strip()

    async def _run_cli_streaming(
        self,
        args: list[str],
        on_line: Any = None,
        no_output_timeout: int | None = None,
    ) -> str:
        """Run a CLI command, calling on_line(text) for each stdout line.

        on_line(text) may return None, or a dict {"stop": True, "question": "..."}
        to stop early (e.g. worker requested feedback); then WorkerNeedsFeedback is raised.

        If no_output_timeout is set and no stdout is received for that many seconds,
        the process is killed and RuntimeError is raised.
        """
        logger.debug("Running (streaming): %s", " ".join(args))
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.work_dir,
        )
        lines: list[str] = []
        reader = proc.stdout
        assert reader is not None
        no_sec = no_output_timeout or 0

        try:
            while True:
                try:
                    if no_sec > 0:
                        raw_line = await asyncio.wait_for(reader.readline(), timeout=no_sec)
                    else:
                        raw_line = await reader.readline()
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
                    raise RuntimeError(
                        f"{args[0]} produced no output for {no_sec}s (killed). "
                        "The agent may be stuck or not writing to stdout."
                    )
                if not raw_line:
                    break
                text = raw_line.decode(errors="replace").rstrip("\n")
                lines.append(text)
                if on_line:
                    out = on_line(text)
                    if isinstance(out, dict) and out.get("stop") and out.get("question"):
                        proc.kill()
                        await proc.wait()
                        raise WorkerNeedsFeedback(out["question"], getattr(self, "name", ""))

            stderr = await proc.stderr.read()
            await proc.wait()
            if proc.returncode != 0:
                err_msg = stderr.decode().strip()
                raise RuntimeError(f"{args[0]} exited with code {proc.returncode}: {err_msg}")
            return "\n".join(lines)
        except WorkerNeedsFeedback:
            raise
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
            raise

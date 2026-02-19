"""Base class for coding agent adapters."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import AsyncIterator

from swarm.config.schema import AgentConfig, AgentType, ApprovalMode

logger = logging.getLogger(__name__)


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
        self, args: list[str], on_line: callable | None = None
    ) -> str:
        """Run a CLI command, calling on_line(text) for each stdout line.

        Returns the full stdout when the process completes.
        """
        logger.debug("Running (streaming): %s", " ".join(args))
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.work_dir,
        )
        lines = []
        async for raw_line in proc.stdout:
            text = raw_line.decode().rstrip("\n")
            lines.append(text)
            if on_line:
                on_line(text)

        stderr = await proc.stderr.read()
        await proc.wait()
        if proc.returncode != 0:
            err_msg = stderr.decode().strip()
            raise RuntimeError(f"{args[0]} exited with code {proc.returncode}: {err_msg}")
        return "\n".join(lines)

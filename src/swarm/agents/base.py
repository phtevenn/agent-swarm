"""Base class for coding agent adapters."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod

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

    @property
    def name(self) -> str:
        return self.config.agent.value

    @abstractmethod
    def _build_cmd(self) -> list[str]:
        """Build the base CLI command including approval-mode flags.

        Each adapter must translate self.approval_mode into the correct
        CLI flags for its underlying tool.
        """

    @abstractmethod
    async def execute(self, title: str, description: str) -> str:
        """Execute a task and return the result as a string."""

    @abstractmethod
    async def decompose(self, prompt: str) -> list[dict]:
        """Break a high-level prompt into a list of subtask dicts.

        Each dict should have at least: {"title": str, "description": str}
        """

    @abstractmethod
    async def synthesize(self, original_prompt: str, results: dict[str, str]) -> str:
        """Synthesize multiple subtask results into a final answer."""

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

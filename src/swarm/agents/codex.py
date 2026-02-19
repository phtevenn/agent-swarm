"""Adapter for OpenAI Codex CLI (codex)."""

from __future__ import annotations

from swarm.config.schema import AgentConfig, AgentType, ApprovalMode

from .base import BaseAgent

_APPROVAL_FLAGS: dict[ApprovalMode, list[str]] = {
    ApprovalMode.FULL_AUTO: ["--full-auto"],
    ApprovalMode.AUTO_EDIT: ["--auto-edit"],
    ApprovalMode.SUGGEST: ["--suggest"],
    ApprovalMode.DEFAULT: [],
}


class CodexAgent(BaseAgent):
    """Wraps the `codex` CLI. Primarily used as a worker agent."""

    agent_type = AgentType.CODEX

    def _build_cmd(self) -> list[str]:
        cmd = ["codex", "--quiet"]
        cmd.extend(_APPROVAL_FLAGS.get(self.approval_mode, []))
        if self.config.model:
            cmd.extend(["--model", self.config.model])
        return cmd

    async def health_check(self) -> bool:
        try:
            await self._run_cli(["codex", "--version"])
            return True
        except Exception:
            return False

    async def send(
        self,
        message: str,
        system_prompt: str | None = None,
        continue_session: bool = False,
    ) -> str:
        return await self.execute(message)

    async def execute(self, task: str, context: str = "") -> str:
        prompt = f"{task}\n\n{context}" if context else task
        return await self._run_cli([*self._build_cmd(), prompt])

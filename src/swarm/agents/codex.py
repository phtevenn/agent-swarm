"""Adapter for OpenAI Codex CLI (codex).

Non-interactive mode uses `codex exec`. Approval mapping:
  full-auto  -> --full-auto  (-a on-request, --sandbox workspace-write)
  auto-edit  -> -a on-request -s workspace-write
  suggest    -> -a untrusted -s read-only
  default    -> (no flags)
"""

from __future__ import annotations

from swarm.config.schema import AgentConfig, AgentType, ApprovalMode

from .base import BaseAgent

_APPROVAL_FLAGS: dict[ApprovalMode, list[str]] = {
    ApprovalMode.FULL_AUTO: ["--full-auto"],
    ApprovalMode.AUTO_EDIT: ["-a", "on-request", "-s", "workspace-write"],
    ApprovalMode.SUGGEST: ["-a", "untrusted", "-s", "read-only"],
    ApprovalMode.DEFAULT: [],
}


class CodexAgent(BaseAgent):
    """Wraps the `codex` CLI. Uses `codex exec` for non-interactive tasks."""

    agent_type = AgentType.CODEX

    def _build_cmd(self) -> list[str]:
        cmd = ["codex", "exec", "--skip-git-repo-check"]
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

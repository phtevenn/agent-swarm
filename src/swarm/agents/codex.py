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
    """Wraps the `codex` CLI."""

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

    async def execute(self, title: str, description: str) -> str:
        prompt = f"{title}\n\n{description}" if description else title
        return await self._run_cli([*self._build_cmd(), prompt])

    async def decompose(self, prompt: str) -> list[dict]:
        return [{"title": prompt, "description": ""}]

    async def synthesize(self, original_prompt: str, results: dict[str, str]) -> str:
        results_text = "\n".join(f"- {tid}: {r[:200]}" for tid, r in results.items())
        prompt = f"Summarize these results for: {original_prompt}\n\n{results_text}"
        return await self._run_cli([*self._build_cmd(), prompt])

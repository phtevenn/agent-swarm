"""Adapter for Claude Code CLI (claude)."""

from __future__ import annotations

import json

from swarm.config.schema import AgentConfig, AgentType, ApprovalMode

from .base import BaseAgent

_APPROVAL_FLAGS: dict[ApprovalMode, list[str]] = {
    ApprovalMode.FULL_AUTO: ["--dangerously-skip-permissions"],
    ApprovalMode.AUTO_EDIT: ["--permission-mode", "acceptEdits"],
    ApprovalMode.SUGGEST: ["--permission-mode", "plan"],
    ApprovalMode.DEFAULT: [],
}


class ClaudeCodeAgent(BaseAgent):
    """Wraps the `claude` CLI.

    Lead mode: conversational with --print and --continue for session continuity.
    Worker mode: one-shot --print for delegated tasks.
    """

    agent_type = AgentType.CLAUDE_CODE

    def _build_cmd(self) -> list[str]:
        cmd = ["claude", "--output-format", "json"]
        cmd.extend(_APPROVAL_FLAGS.get(self.approval_mode, []))
        if self.config.model:
            cmd.extend(["--model", self.config.model])
        return cmd

    async def health_check(self) -> bool:
        try:
            await self._run_cli(["claude", "--version"])
            return True
        except Exception:
            return False

    async def send(
        self,
        message: str,
        system_prompt: str | None = None,
        continue_session: bool = False,
    ) -> str:
        cmd = self._build_cmd()
        if system_prompt:
            cmd.extend(["--append-system-prompt", system_prompt])
        if continue_session and self._session_started:
            cmd.append("--continue")
        cmd.extend(["--print", message])

        raw = await self._run_cli(cmd)
        self._session_started = True
        return self._extract_result(raw)

    async def execute(self, task: str, context: str = "") -> str:
        prompt = f"{task}\n\n{context}" if context else task
        raw = await self._run_cli([*self._build_cmd(), "--print", prompt])
        return self._extract_result(raw)

    def _extract_result(self, raw: str) -> str:
        """Extract text from claude JSON output, falling back to raw string."""
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data.get("result", data.get("text", raw))
        except json.JSONDecodeError:
            pass
        return raw

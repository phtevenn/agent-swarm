"""Adapter for Cursor Agent CLI (agent).

The `agent` command provides a headless coding agent with --print mode
for non-interactive use. Permission levels map to:
  full-auto  -> --yolo --trust  (execute everything without prompting)
  auto-edit  -> --trust         (default tool access, trust workspace)
  suggest    -> --mode plan     (read-only planning, no edits)
"""

from __future__ import annotations

import json

from swarm.config.schema import AgentConfig, AgentType, ApprovalMode

from .base import BaseAgent

_APPROVAL_FLAGS: dict[ApprovalMode, list[str]] = {
    ApprovalMode.FULL_AUTO: ["--yolo", "--trust"],
    ApprovalMode.AUTO_EDIT: ["--trust"],
    ApprovalMode.SUGGEST: ["--mode", "plan", "--trust"],
    ApprovalMode.DEFAULT: [],
}


class CursorAgent(BaseAgent):
    """Wraps the `agent` CLI (Cursor Agent).

    Lead mode: conversational with --print and --continue for session continuity.
    Worker mode: one-shot --print for delegated tasks.
    """

    agent_type = AgentType.CURSOR

    def _build_cmd(self) -> list[str]:
        cmd = ["agent", "--print", "--output-format", "json"]
        cmd.extend(_APPROVAL_FLAGS.get(self.approval_mode, []))
        if self.config.model:
            cmd.extend(["--model", self.config.model])
        return cmd

    async def health_check(self) -> bool:
        try:
            await self._run_cli(["agent", "--version"])
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
        if continue_session and self._session_started:
            cmd.append("--continue")
        cmd.append(message)

        raw = await self._run_cli(cmd)
        self._session_started = True
        return self._extract_result(raw)

    async def execute(self, task: str, context: str = "") -> str:
        prompt = f"{task}\n\n{context}" if context else task
        raw = await self._run_cli([*self._build_cmd(), prompt])
        return self._extract_result(raw)

    def _extract_result(self, raw: str) -> str:
        """Extract text from agent JSON output, falling back to raw string."""
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data.get("result", data.get("text", raw))
        except json.JSONDecodeError:
            pass
        return raw

"""Adapter for Cursor Agent CLI (agent).

The `agent` command provides a headless coding agent with --print mode
for non-interactive use. Permission levels map to:
  full-auto  → --yolo --trust  (execute everything without prompting)
  auto-edit  → --trust         (default tool access, trust workspace)
  suggest    → --mode plan     (read-only planning, no edits)
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
    """Wraps the `agent` CLI (Cursor Agent) in non-interactive print mode."""

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

    async def execute(self, title: str, description: str) -> str:
        prompt = f"{title}\n\n{description}" if description else title
        raw = await self._run_cli([*self._build_cmd(), prompt])
        return self._extract_result(raw)

    async def decompose(self, prompt: str) -> list[dict]:
        full_prompt = (
            "Break this task into smaller independent subtasks. "
            "Return a JSON array of objects with 'title' and 'description' fields. "
            "Return ONLY valid JSON.\n\n"
            f"Task: {prompt}"
        )
        raw = await self._run_cli([*self._build_cmd(), full_prompt])
        text = self._extract_result(raw)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
            return [{"title": prompt, "description": ""}]

    async def synthesize(self, original_prompt: str, results: dict[str, str]) -> str:
        results_text = "\n\n".join(
            f"## Subtask {tid}\n{result}" for tid, result in results.items()
        )
        prompt = (
            f"Synthesize these subtask results for the original task: {original_prompt}\n\n"
            f"{results_text}"
        )
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

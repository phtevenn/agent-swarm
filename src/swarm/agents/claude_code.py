"""Adapter for Claude Code CLI (claude)."""

from __future__ import annotations

import json

from swarm.config.schema import AgentConfig, AgentType, ApprovalMode

from .base import BaseAgent

DECOMPOSE_SYSTEM = (
    "You are a task decomposer. Given a high-level coding task, break it into "
    "smaller independent subtasks that can be delegated to different agents. "
    "Return a JSON array of objects with 'title' and 'description' fields. "
    "Return ONLY valid JSON, no markdown."
)

SYNTHESIZE_SYSTEM = (
    "You are a result synthesizer. Given the original task and results from "
    "multiple subtasks, produce a concise summary of what was accomplished."
)

_APPROVAL_FLAGS: dict[ApprovalMode, list[str]] = {
    ApprovalMode.FULL_AUTO: ["--dangerously-skip-permissions"],
    ApprovalMode.AUTO_EDIT: ["--permission-mode", "acceptEdits"],
    ApprovalMode.SUGGEST: ["--permission-mode", "plan"],
    ApprovalMode.DEFAULT: [],
}


class ClaudeCodeAgent(BaseAgent):
    """Wraps the `claude` CLI in non-interactive (pipe) mode."""

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

    async def execute(self, title: str, description: str) -> str:
        prompt = f"{title}\n\n{description}" if description else title
        raw = await self._run_cli([*self._build_cmd(), "--print", prompt])
        return self._extract_result(raw)

    async def decompose(self, prompt: str) -> list[dict]:
        full_prompt = (
            f"System: {DECOMPOSE_SYSTEM}\n\n"
            f"Task: {prompt}\n\n"
            "Respond with a JSON array only."
        )
        raw = await self._run_cli([*self._build_cmd(), "--print", full_prompt])
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
            f"System: {SYNTHESIZE_SYSTEM}\n\n"
            f"Original task: {original_prompt}\n\n"
            f"Subtask results:\n{results_text}"
        )
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

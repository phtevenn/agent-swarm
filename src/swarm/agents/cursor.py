"""Adapter for Cursor Agent.

Cursor doesn't expose a non-interactive CLI in the same way as Claude Code
or Codex. This adapter works by writing a task prompt to a file and invoking
Cursor's terminal command. Richer integration (Phase 2) will use the Cursor
background agent API once available.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from swarm.config.schema import AgentConfig, AgentType

from .base import BaseAgent


class CursorAgent(BaseAgent):
    """Wraps the Cursor editor's agent capabilities.

    Current approach: use `cursor` CLI to open a workspace with a task prompt
    file. This is a scaffolded adapter — full integration depends on Cursor
    exposing a headless/background agent API.
    """

    agent_type = AgentType.CURSOR

    def __init__(self, config: AgentConfig, work_dir: str = ".") -> None:
        super().__init__(config, work_dir)

    async def health_check(self) -> bool:
        try:
            await self._run_cli(["cursor", "--version"])
            return True
        except Exception:
            return False

    async def execute(self, title: str, description: str) -> str:
        prompt = f"# Task: {title}\n\n{description}" if description else f"# Task: {title}"
        prompt_file = Path(tempfile.mktemp(suffix=".md", prefix="swarm_task_"))
        prompt_file.write_text(prompt)
        try:
            result = await self._run_cli(
                ["cursor", "--goto", str(prompt_file)],
            )
            return result or f"[cursor] Task prompt delivered: {title}"
        finally:
            prompt_file.unlink(missing_ok=True)

    async def decompose(self, prompt: str) -> list[dict]:
        return [{"title": prompt, "description": ""}]

    async def synthesize(self, original_prompt: str, results: dict[str, str]) -> str:
        return "\n\n".join(f"## {tid}\n{r}" for tid, r in results.items())

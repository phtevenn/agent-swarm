"""Adapter for OpenAI Codex CLI (codex)."""

from __future__ import annotations

import json

from swarm.config.schema import AgentConfig, AgentType

from .base import BaseAgent


class CodexAgent(BaseAgent):
    """Wraps the `codex` CLI."""

    agent_type = AgentType.CODEX

    def __init__(self, config: AgentConfig, work_dir: str = ".") -> None:
        super().__init__(config, work_dir)
        self._base_cmd = ["codex", "--quiet", "--full-auto"]
        if config.model:
            self._base_cmd.extend(["--model", config.model])

    async def health_check(self) -> bool:
        try:
            await self._run_cli(["codex", "--version"])
            return True
        except Exception:
            return False

    async def execute(self, title: str, description: str) -> str:
        prompt = f"{title}\n\n{description}" if description else title
        return await self._run_cli([*self._base_cmd, prompt])

    async def decompose(self, prompt: str) -> list[dict]:
        # Codex is typically used as a worker, not a decomposer.
        # Fallback: return the whole task as a single item.
        return [{"title": prompt, "description": ""}]

    async def synthesize(self, original_prompt: str, results: dict[str, str]) -> str:
        results_text = "\n".join(f"- {tid}: {r[:200]}" for tid, r in results.items())
        prompt = f"Summarize these results for: {original_prompt}\n\n{results_text}"
        return await self._run_cli([*self._base_cmd, prompt])

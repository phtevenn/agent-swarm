"""Discord bot for agent swarm status updates.

Phase 2 — sends notifications to a Discord channel when tasks start,
complete, or fail. Each agent gets its own thread or message prefix.

Requires: pip install discord.py  (or `uv sync --extra discord`)
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from swarm.config.schema import DiscordConfig
    from swarm.core.task import Task

logger = logging.getLogger(__name__)


class SwarmDiscordBot:
    """Lightweight Discord bot that posts swarm status updates."""

    def __init__(self, config: DiscordConfig) -> None:
        self.config = config
        self._client = None
        self._channel = None
        self._ready = asyncio.Event()

    async def start(self) -> None:
        """Connect to Discord. Call this before posting updates."""
        if not self.config.enabled:
            logger.info("Discord integration disabled in config.")
            return

        try:
            import discord
        except ImportError:
            logger.error(
                "discord.py not installed. Run: uv sync --extra discord"
            )
            return

        import os

        token = os.environ.get(self.config.token_env)
        if not token:
            logger.error("Discord token not found in env var %s", self.config.token_env)
            return

        intents = discord.Intents.default()
        intents.message_content = True
        self._client = discord.Client(intents=intents)

        @self._client.event
        async def on_ready() -> None:
            if self.config.channel_id:
                self._channel = self._client.get_channel(self.config.channel_id)
            logger.info("Discord bot connected as %s", self._client.user)
            self._ready.set()

        asyncio.create_task(self._client.start(token))
        await self._ready.wait()

    async def notify_task_event(self, event: str, task: Task, agent_name: str = "") -> None:
        """Post a task event notification if the event type is in notify_on."""
        if not self.config.enabled or self._channel is None:
            return

        if event not in self.config.notify_on:
            return

        emoji = {"task_started": "▶️", "task_completed": "✅", "task_failed": "❌"}.get(
            event, "ℹ️"
        )
        msg = f"{emoji} **{event}** | `{task.id}` — {task.title}"
        if agent_name:
            msg += f" (agent: `{agent_name}`)"
        if event == "task_failed" and task.error:
            msg += f"\n> Error: {task.error}"

        try:
            await self._channel.send(msg)
        except Exception:
            logger.exception("Failed to send Discord notification")

    async def post_status_summary(self, statuses: dict[str, dict]) -> None:
        """Post a summary of all agent statuses."""
        if not self.config.enabled or self._channel is None:
            return

        lines = ["**Agent Swarm Status**"]
        for name, info in statuses.items():
            state = info.get("state", "unknown")
            icon = "🟢" if state == "idle" else "🔵" if state == "working" else "⚪"
            lines.append(f"{icon} `{name}`: {state}")

        try:
            await self._channel.send("\n".join(lines))
        except Exception:
            logger.exception("Failed to send Discord status summary")

    async def stop(self) -> None:
        if self._client and not self._client.is_closed():
            await self._client.close()

"""Tmux-based terminal manager for multi-agent window layout.

Phase 2 — creates a tmux session with one pane per agent so the human
can observe all agents working simultaneously.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from swarm.config.schema import TerminalLayout

logger = logging.getLogger(__name__)


@dataclass
class TmuxPane:
    agent_name: str
    pane_id: str = ""
    pid: int | None = None


class TmuxManager:
    """Manage a tmux session with panes for each agent."""

    SESSION_NAME = "agent-swarm"

    def __init__(self, layout: TerminalLayout = TerminalLayout.TILED) -> None:
        self.layout = layout
        self.panes: dict[str, TmuxPane] = {}

    async def create_session(self, agent_names: list[str]) -> None:
        """Create a tmux session with one pane per agent."""
        await self._run(["tmux", "new-session", "-d", "-s", self.SESSION_NAME, "-n", "swarm"])

        for i, name in enumerate(agent_names):
            if i > 0:
                await self._run([
                    "tmux", "split-window", "-t", self.SESSION_NAME, "-h"
                ])
            pane_id = await self._run([
                "tmux", "display-message", "-t", self.SESSION_NAME, "-p", "#{pane_id}"
            ])
            self.panes[name] = TmuxPane(agent_name=name, pane_id=pane_id.strip())

        layout_arg = {
            TerminalLayout.TILED: "tiled",
            TerminalLayout.HORIZONTAL: "even-horizontal",
            TerminalLayout.VERTICAL: "even-vertical",
        }.get(self.layout, "tiled")

        await self._run([
            "tmux", "select-layout", "-t", self.SESSION_NAME, layout_arg
        ])
        logger.info("Tmux session '%s' created with %d panes", self.SESSION_NAME, len(agent_names))

    async def send_to_agent(self, agent_name: str, command: str) -> None:
        """Send a command to a specific agent's pane."""
        pane = self.panes.get(agent_name)
        if pane is None:
            logger.warning("No pane for agent '%s'", agent_name)
            return
        await self._run([
            "tmux", "send-keys", "-t", pane.pane_id, command, "Enter"
        ])

    async def attach(self) -> None:
        """Print instructions to attach to the session."""
        logger.info("Attach to session: tmux attach -t %s", self.SESSION_NAME)

    async def kill_session(self) -> None:
        """Destroy the tmux session."""
        try:
            await self._run(["tmux", "kill-session", "-t", self.SESSION_NAME])
        except RuntimeError:
            pass

    async def _run(self, args: list[str]) -> str:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"tmux command failed: {stderr.decode().strip()}")
        return stdout.decode()

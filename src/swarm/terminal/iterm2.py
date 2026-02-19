"""iTerm2-based terminal manager for multi-agent window layout.

Phase 2 — uses the iTerm2 Python API to create tabs/splits for each agent.

Requires: pip install iterm2  (or `uv sync --extra iterm2`)
Also requires iTerm2 to be running with the Python API enabled
(Preferences > General > Magic > Enable Python API).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class ITermManager:
    """Manage iTerm2 tabs/panes for each agent.

    Scaffolded — implementation requires the iterm2 Python package
    and a running iTerm2 instance with the Python API enabled.
    """

    def __init__(self) -> None:
        self.sessions: dict[str, object] = {}

    async def create_layout(self, agent_names: list[str]) -> None:
        """Create an iTerm2 window with one tab per agent."""
        try:
            import iterm2
        except ImportError:
            logger.error("iterm2 package not installed. Run: uv sync --extra iterm2")
            return

        connection = await iterm2.Connection.async_create()
        app = await iterm2.async_get_app(connection)
        window = app.current_window

        if window is None:
            logger.error("No iTerm2 window found. Is iTerm2 running?")
            return

        for i, name in enumerate(agent_names):
            if i == 0:
                session = window.current_tab.current_session
            else:
                tab = await window.async_create_tab()
                session = tab.current_session

            await session.async_set_name(f"swarm: {name}")
            self.sessions[name] = session
            logger.info("Created iTerm2 tab for agent '%s'", name)

    async def send_to_agent(self, agent_name: str, text: str) -> None:
        """Send text to a specific agent's iTerm2 session."""
        session = self.sessions.get(agent_name)
        if session is None:
            logger.warning("No iTerm2 session for agent '%s'", agent_name)
            return
        await session.async_send_text(text + "\n")

    async def close_all(self) -> None:
        """Close all agent sessions."""
        for name, session in self.sessions.items():
            try:
                await session.async_close()
            except Exception:
                logger.warning("Failed to close iTerm2 session for '%s'", name)
        self.sessions.clear()

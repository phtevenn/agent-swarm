"""File-based message bus for inter-agent communication.

Messages are JSON files written to .swarm/ subdirectories.
Agents watch for new files and process them.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

from watchfiles import awatch, Change

from .task import Task

logger = logging.getLogger(__name__)


class MessageBus:
    """File-system message bus rooted at a .swarm/ directory."""

    def __init__(self, bus_dir: Path) -> None:
        self.bus_dir = Path(bus_dir)
        self.tasks_dir = self.bus_dir / "tasks"
        self.status_dir = self.bus_dir / "status"
        self.messages_dir = self.bus_dir / "messages"
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        for d in (self.tasks_dir, self.status_dir, self.messages_dir):
            d.mkdir(parents=True, exist_ok=True)

    def publish_task(self, task: Task) -> Path:
        """Write a task to the tasks directory. Returns the file path."""
        path = self.tasks_dir / f"{task.id}.json"
        path.write_text(task.model_dump_json(indent=2))
        logger.info("Published task %s -> %s", task.id, path)
        return path

    def read_task(self, task_id: str) -> Task | None:
        """Read a task by ID from the tasks directory."""
        path = self.tasks_dir / f"{task_id}.json"
        if not path.exists():
            return None
        return Task.model_validate_json(path.read_text())

    def list_tasks(self) -> list[Task]:
        """List all tasks in the tasks directory."""
        tasks = []
        for path in sorted(self.tasks_dir.glob("*.json")):
            try:
                tasks.append(Task.model_validate_json(path.read_text()))
            except Exception:
                logger.warning("Skipping malformed task file: %s", path)
        return tasks

    def update_status(self, agent_name: str, status: dict) -> Path:
        """Write an agent status update."""
        status["agent"] = agent_name
        status["timestamp"] = datetime.now(timezone.utc).isoformat()
        path = self.status_dir / f"{agent_name}.json"
        path.write_text(json.dumps(status, indent=2))
        return path

    def read_status(self, agent_name: str) -> dict | None:
        """Read the latest status for an agent."""
        path = self.status_dir / f"{agent_name}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def post_message(self, from_agent: str, to_agent: str, content: str) -> Path:
        """Post an inter-agent message."""
        ts = datetime.now(timezone.utc)
        slug = ts.strftime("%Y%m%d_%H%M%S_%f")
        msg = {
            "from": from_agent,
            "to": to_agent,
            "content": content,
            "timestamp": ts.isoformat(),
        }
        path = self.messages_dir / f"{slug}_{from_agent}_to_{to_agent}.json"
        path.write_text(json.dumps(msg, indent=2))
        return path

    async def watch_tasks(self) -> AsyncIterator[tuple[Change, str]]:
        """Yield (change_type, path) whenever task files are created or modified."""
        async for changes in awatch(self.tasks_dir):
            for change_type, path in changes:
                yield change_type, path

    async def watch_status(self) -> AsyncIterator[tuple[Change, str]]:
        """Yield (change_type, path) whenever status files change."""
        async for changes in awatch(self.status_dir):
            for change_type, path in changes:
                yield change_type, path

    def cleanup(self) -> None:
        """Remove all bus files (useful for tests)."""
        for d in (self.tasks_dir, self.status_dir, self.messages_dir):
            for f in d.glob("*.json"):
                f.unlink()

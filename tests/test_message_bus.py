"""Tests for the file-based message bus."""

import tempfile
from pathlib import Path

import pytest

from swarm.core.message_bus import MessageBus
from swarm.core.task import Task


@pytest.fixture
def bus(tmp_path: Path) -> MessageBus:
    return MessageBus(tmp_path / ".swarm")


def test_publish_and_read_task(bus: MessageBus):
    task = Task(title="test task", description="do the thing")
    bus.publish_task(task)

    loaded = bus.read_task(task.id)
    assert loaded is not None
    assert loaded.id == task.id
    assert loaded.title == "test task"


def test_list_tasks(bus: MessageBus):
    for i in range(3):
        bus.publish_task(Task(title=f"task {i}"))
    tasks = bus.list_tasks()
    assert len(tasks) == 3


def test_read_missing_task(bus: MessageBus):
    assert bus.read_task("nonexistent") is None


def test_status_updates(bus: MessageBus):
    bus.update_status("codex", {"state": "working", "task_id": "abc"})
    status = bus.read_status("codex")
    assert status is not None
    assert status["state"] == "working"
    assert status["agent"] == "codex"


def test_post_message(bus: MessageBus):
    path = bus.post_message("lead", "worker1", "do this subtask")
    assert path.exists()
    import json
    msg = json.loads(path.read_text())
    assert msg["from"] == "lead"
    assert msg["to"] == "worker1"


def test_cleanup(bus: MessageBus):
    bus.publish_task(Task(title="temp"))
    bus.update_status("test", {"state": "idle"})
    bus.cleanup()
    assert bus.list_tasks() == []
    assert bus.read_status("test") is None

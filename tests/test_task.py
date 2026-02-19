"""Tests for the Task model."""

from swarm.core.task import Task, TaskStatus


def test_task_defaults():
    task = Task(title="test task")
    assert task.status == TaskStatus.PENDING
    assert task.created_by == "human"
    assert task.assigned_to is None
    assert len(task.id) == 12


def test_task_lifecycle():
    task = Task(title="do something")
    task.assign("codex")
    assert task.status == TaskStatus.ASSIGNED
    assert task.assigned_to == "codex"

    task.start()
    assert task.status == TaskStatus.IN_PROGRESS

    task.complete("done")
    assert task.status == TaskStatus.COMPLETED
    assert task.result == "done"


def test_task_failure():
    task = Task(title="will fail")
    task.assign("cursor")
    task.start()
    task.fail("something went wrong")
    assert task.status == TaskStatus.FAILED
    assert task.error == "something went wrong"


def test_task_cancel():
    task = Task(title="to cancel")
    task.cancel()
    assert task.status == TaskStatus.CANCELLED

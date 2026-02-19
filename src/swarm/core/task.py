"""Task model for swarm orchestration."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task(BaseModel):
    """A unit of work assigned to an agent."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    parent_id: str | None = None
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    assigned_to: str | None = None
    created_by: str = "human"
    result: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def assign(self, agent_name: str) -> None:
        self.assigned_to = agent_name
        self.status = TaskStatus.ASSIGNED
        self._touch()

    def start(self) -> None:
        self.status = TaskStatus.IN_PROGRESS
        self._touch()

    def complete(self, result: str) -> None:
        self.result = result
        self.status = TaskStatus.COMPLETED
        self._touch()

    def fail(self, error: str) -> None:
        self.error = error
        self.status = TaskStatus.FAILED
        self._touch()

    def cancel(self) -> None:
        self.status = TaskStatus.CANCELLED
        self._touch()

    def _touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)

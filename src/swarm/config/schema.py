"""Pydantic models for swarm configuration."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class AgentType(str, Enum):
    CLAUDE_CODE = "claude-code"
    CODEX = "codex"
    CURSOR = "cursor"


class ApprovalMode(str, Enum):
    """Controls how much autonomy agents have.

    Set at the swarm level — all agents (lead + workers) inherit the same mode.
    """

    FULL_AUTO = "full-auto"  # No human approval; agents execute everything
    AUTO_EDIT = "auto-edit"  # Auto-approve file edits, prompt for shell commands
    SUGGEST = "suggest"      # Read-only / plan mode; agents propose but don't execute
    DEFAULT = "default"      # Each agent's built-in default behavior


class AgentConfig(BaseModel):
    agent: AgentType
    enabled: bool = True
    model: str | None = None
    timeout: int = 300
    max_concurrent_tasks: int = 2


class TaskSettings(BaseModel):
    worker_timeout: int = 600
    max_parallel: int = 4


class DiscordConfig(BaseModel):
    enabled: bool = False
    token_env: str = "DISCORD_BOT_TOKEN"
    channel_id: int | None = None
    notify_on: list[str] = Field(
        default_factory=lambda: ["task_started", "task_completed", "task_failed"]
    )


class TerminalBackend(str, Enum):
    TMUX = "tmux"
    ITERM2 = "iterm2"


class TerminalLayout(str, Enum):
    TILED = "tiled"
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


class TerminalConfig(BaseModel):
    backend: TerminalBackend = TerminalBackend.TMUX
    layout: TerminalLayout = TerminalLayout.TILED


class SwarmConfig(BaseModel):
    bus_dir: Path = Path(".swarm")
    approval_mode: ApprovalMode = ApprovalMode.FULL_AUTO
    lead: AgentConfig
    workers: list[AgentConfig] = Field(default_factory=list)
    tasks: TaskSettings = Field(default_factory=TaskSettings)


class Config(BaseModel):
    """Top-level configuration."""

    swarm: SwarmConfig
    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    terminal: TerminalConfig = Field(default_factory=TerminalConfig)

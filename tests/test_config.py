"""Tests for config loading and validation."""

from pathlib import Path

import pytest

from swarm.config import load_config
from swarm.config.schema import AgentType, Config


def test_load_default_config():
    config = load_config("config/swarm.yaml")
    assert isinstance(config, Config)
    assert config.swarm.lead.agent == AgentType.CLAUDE_CODE
    assert len(config.swarm.workers) == 2


def test_load_missing_file():
    with pytest.raises(FileNotFoundError):
        load_config("nonexistent.yaml")


def test_config_defaults():
    config = load_config("config/swarm.yaml")
    assert config.swarm.tasks.worker_timeout == 600
    assert config.swarm.tasks.max_parallel == 4
    assert config.discord.enabled is False
    assert config.swarm.bus_dir == Path(".swarm")

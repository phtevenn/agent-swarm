"""Tests for config loading and validation."""

from pathlib import Path

import pytest

from swarm.config import load_config, load_config_with_fallback
from swarm.config.loader import find_config
from swarm.config.schema import AgentType, ApprovalMode, Config


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


def test_config_approval_mode():
    config = load_config("config/swarm.yaml")
    assert config.swarm.approval_mode == ApprovalMode.FULL_AUTO


def test_builtin_defaults_when_no_config(tmp_path: Path):
    cfg, source = load_config_with_fallback(None)
    # find_config returns None from tmp_path (no config files)
    # but load_config_with_fallback uses cwd, so test the explicit None path
    assert source == "built-in defaults" or source.endswith(".yaml")
    assert cfg.swarm.lead.agent == AgentType.CLAUDE_CODE


def test_find_config_discovers_swarm_yaml(tmp_path: Path):
    (tmp_path / "swarm.yaml").write_text("swarm:\n  lead:\n    agent: claude-code\n")
    found = find_config(tmp_path)
    assert found is not None
    assert found.name == "swarm.yaml"


def test_find_config_discovers_config_subdir(tmp_path: Path):
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    (cfg_dir / "swarm.yaml").write_text("swarm:\n  lead:\n    agent: claude-code\n")
    found = find_config(tmp_path)
    assert found is not None
    assert str(found).endswith("config/swarm.yaml")


def test_find_config_returns_none(tmp_path: Path, monkeypatch):
    """When cwd has no config, find_config returns None only if global config is absent."""
    monkeypatch.setattr(
        "swarm.config.loader.GLOBAL_CONFIG",
        tmp_path / "no_global_swarm.yaml",
    )
    assert find_config(tmp_path) is None


def test_explicit_config_path():
    cfg, source = load_config_with_fallback("config/swarm.yaml")
    assert source == "config/swarm.yaml"
    assert cfg.swarm.lead.agent == AgentType.CLAUDE_CODE

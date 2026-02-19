"""Load and validate swarm configuration from YAML."""

from __future__ import annotations

from pathlib import Path

import yaml

from .schema import Config

GLOBAL_CONFIG = Path.home() / ".config" / "agent-swarm" / "swarm.yaml"

SEARCH_ORDER = [
    lambda cwd: cwd / "swarm.yaml",
    lambda cwd: cwd / "config" / "swarm.yaml",
    lambda _: GLOBAL_CONFIG,
]


def find_config(cwd: Path | None = None) -> Path | None:
    """Search for a config file in standard locations. Returns None if not found."""
    cwd = cwd or Path.cwd()
    for resolver in SEARCH_ORDER:
        candidate = resolver(cwd)
        if candidate.exists():
            return candidate
    return None


def load_config(path: str | Path) -> Config:
    """Load configuration from a YAML file and validate it."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path) as f:
        raw = yaml.safe_load(f)

    if raw is None:
        raise ValueError(f"Config file is empty: {path}")

    return Config.model_validate(raw)


def load_config_with_fallback(explicit: str | None = None) -> tuple[Config, str]:
    """Load config from explicit path, auto-discovered file, or built-in defaults.

    Returns (config, source) where source describes where config came from.
    """
    if explicit:
        return load_config(explicit), explicit

    found = find_config()
    if found:
        return load_config(found), str(found)

    return Config.model_validate({"swarm": {}}), "built-in defaults"

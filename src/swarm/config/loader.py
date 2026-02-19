"""Load and validate swarm configuration from YAML."""

from __future__ import annotations

from pathlib import Path

import yaml

from .schema import Config


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

"""Workspace trust system.

Since swarm bypasses each agent's individual trust/permission check
(e.g. --dangerously-skip-permissions, --yolo --trust), we need our own
gate before granting elevated access to a workspace.

Trusted workspaces are stored in ~/.config/agent-swarm/trusted.json.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from swarm.config.schema import ApprovalMode

logger = logging.getLogger(__name__)

TRUST_DIR = Path.home() / ".config" / "agent-swarm"
TRUST_FILE = TRUST_DIR / "trusted.json"

_MODES_REQUIRING_TRUST = {ApprovalMode.FULL_AUTO, ApprovalMode.AUTO_EDIT}


def _load_trusted() -> dict:
    if not TRUST_FILE.exists():
        return {"workspaces": []}
    try:
        return json.loads(TRUST_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {"workspaces": []}


def _save_trusted(data: dict) -> None:
    TRUST_DIR.mkdir(parents=True, exist_ok=True)
    TRUST_FILE.write_text(json.dumps(data, indent=2))


def is_workspace_trusted(workspace: Path) -> bool:
    """Check if a workspace has been previously trusted."""
    resolved = str(workspace.resolve())
    data = _load_trusted()
    return resolved in data.get("workspaces", [])


def trust_workspace(workspace: Path) -> None:
    """Mark a workspace as trusted."""
    resolved = str(workspace.resolve())
    data = _load_trusted()
    workspaces = data.get("workspaces", [])
    if resolved not in workspaces:
        workspaces.append(resolved)
        data["workspaces"] = workspaces
        _save_trusted(data)
        logger.info("Trusted workspace: %s", resolved)


def revoke_trust(workspace: Path) -> bool:
    """Remove trust for a workspace. Returns True if it was previously trusted."""
    resolved = str(workspace.resolve())
    data = _load_trusted()
    workspaces = data.get("workspaces", [])
    if resolved in workspaces:
        workspaces.remove(resolved)
        data["workspaces"] = workspaces
        _save_trusted(data)
        return True
    return False


def requires_trust(approval_mode: ApprovalMode) -> bool:
    """Whether the given approval mode requires workspace trust."""
    return approval_mode in _MODES_REQUIRING_TRUST

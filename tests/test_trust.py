"""Tests for the workspace trust system."""

from pathlib import Path
from unittest.mock import patch

import pytest

from swarm.config.schema import ApprovalMode
from swarm.core.trust import (
    is_workspace_trusted,
    requires_trust,
    revoke_trust,
    trust_workspace,
)


@pytest.fixture(autouse=True)
def isolated_trust_file(tmp_path: Path, monkeypatch):
    """Redirect trust storage to a temp directory for every test."""
    trust_dir = tmp_path / ".config" / "agent-swarm"
    trust_file = trust_dir / "trusted.json"
    monkeypatch.setattr("swarm.core.trust.TRUST_DIR", trust_dir)
    monkeypatch.setattr("swarm.core.trust.TRUST_FILE", trust_file)


def test_untrusted_by_default(tmp_path: Path):
    assert is_workspace_trusted(tmp_path / "some-repo") is False


def test_trust_and_check(tmp_path: Path):
    workspace = tmp_path / "my-repo"
    workspace.mkdir()
    trust_workspace(workspace)
    assert is_workspace_trusted(workspace) is True


def test_revoke_trust(tmp_path: Path):
    workspace = tmp_path / "my-repo"
    workspace.mkdir()
    trust_workspace(workspace)
    assert revoke_trust(workspace) is True
    assert is_workspace_trusted(workspace) is False


def test_revoke_untrusted_returns_false(tmp_path: Path):
    workspace = tmp_path / "never-trusted"
    assert revoke_trust(workspace) is False


def test_trust_is_idempotent(tmp_path: Path):
    workspace = tmp_path / "repo"
    workspace.mkdir()
    trust_workspace(workspace)
    trust_workspace(workspace)
    assert is_workspace_trusted(workspace) is True


def test_multiple_workspaces(tmp_path: Path):
    ws1 = tmp_path / "repo1"
    ws2 = tmp_path / "repo2"
    ws1.mkdir()
    ws2.mkdir()
    trust_workspace(ws1)
    assert is_workspace_trusted(ws1) is True
    assert is_workspace_trusted(ws2) is False
    trust_workspace(ws2)
    assert is_workspace_trusted(ws2) is True


def test_requires_trust_full_auto():
    assert requires_trust(ApprovalMode.FULL_AUTO) is True


def test_requires_trust_auto_edit():
    assert requires_trust(ApprovalMode.AUTO_EDIT) is True


def test_no_trust_needed_for_suggest():
    assert requires_trust(ApprovalMode.SUGGEST) is False


def test_no_trust_needed_for_default():
    assert requires_trust(ApprovalMode.DEFAULT) is False

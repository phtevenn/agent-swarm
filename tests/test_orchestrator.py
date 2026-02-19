"""Tests for the orchestrator's delegation detection and system prompt."""

import json

from swarm.agents import create_agent
from swarm.config.schema import AgentConfig, AgentType, ApprovalMode
from swarm.core.orchestrator import DELEGATE_PATTERN, _build_system_prompt


def test_delegate_pattern_matches():
    text = (
        'Here is my plan.\n\n'
        '<swarm:delegate>\n'
        '[{"agent": "codex", "task": "write tests"}]\n'
        '</swarm:delegate>\n\n'
        'I will review the results.'
    )
    match = DELEGATE_PATTERN.search(text)
    assert match is not None
    parsed = json.loads(match.group(1))
    assert len(parsed) == 1
    assert parsed[0]["agent"] == "codex"
    assert parsed[0]["task"] == "write tests"


def test_delegate_pattern_no_match():
    assert DELEGATE_PATTERN.search("Just a normal response.") is None


def test_delegate_pattern_multiple_tasks():
    block = (
        '<swarm:delegate>\n'
        '[\n'
        '  {"agent": "codex", "task": "task one"},\n'
        '  {"agent": "cursor", "task": "task two"}\n'
        ']\n'
        '</swarm:delegate>'
    )
    match = DELEGATE_PATTERN.search(block)
    assert match is not None
    parsed = json.loads(match.group(1))
    assert len(parsed) == 2


def test_delegate_pattern_strips_from_response():
    response = "Before delegation.\n\n<swarm:delegate>[{\"agent\":\"codex\",\"task\":\"x\"}]</swarm:delegate>\n\nAfter delegation."
    cleaned = DELEGATE_PATTERN.sub("", response).strip()
    assert "<swarm:delegate>" not in cleaned
    assert "Before delegation." in cleaned
    assert "After delegation." in cleaned


def test_build_system_prompt_with_workers():
    workers = {
        "codex": create_agent(AgentConfig(agent=AgentType.CODEX)),
        "cursor": create_agent(AgentConfig(agent=AgentType.CURSOR)),
    }
    prompt = _build_system_prompt(workers)
    assert "codex" in prompt
    assert "cursor" in prompt
    assert "<swarm:delegate>" in prompt


def test_build_system_prompt_empty_workers():
    prompt = _build_system_prompt({})
    assert prompt == ""


def test_build_system_prompt_skips_disabled():
    workers = {
        "codex": create_agent(AgentConfig(agent=AgentType.CODEX, enabled=False)),
        "cursor": create_agent(AgentConfig(agent=AgentType.CURSOR, enabled=True)),
    }
    prompt = _build_system_prompt(workers)
    assert "cursor" in prompt
    # codex is disabled, should not appear in the worker list
    lines = [l.strip() for l in prompt.split("\n") if l.strip().startswith("- ")]
    agent_names = [l.lstrip("- ") for l in lines]
    assert "codex" not in agent_names

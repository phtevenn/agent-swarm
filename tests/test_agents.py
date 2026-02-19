"""Tests for agent factory and registry."""

import pytest

from swarm.agents import AGENT_REGISTRY, create_agent
from swarm.agents.base import BaseAgent
from swarm.agents.claude_code import ClaudeCodeAgent
from swarm.agents.codex import CodexAgent
from swarm.agents.cursor import CursorAgent
from swarm.config.schema import AgentConfig, AgentType


def test_registry_has_all_agents():
    assert AgentType.CLAUDE_CODE in AGENT_REGISTRY
    assert AgentType.CODEX in AGENT_REGISTRY
    assert AgentType.CURSOR in AGENT_REGISTRY


def test_create_claude_code():
    agent = create_agent(AgentConfig(agent=AgentType.CLAUDE_CODE))
    assert isinstance(agent, ClaudeCodeAgent)
    assert agent.name == "claude-code"


def test_create_codex():
    agent = create_agent(AgentConfig(agent=AgentType.CODEX))
    assert isinstance(agent, CodexAgent)
    assert agent.name == "codex"


def test_create_cursor():
    agent = create_agent(AgentConfig(agent=AgentType.CURSOR))
    assert isinstance(agent, CursorAgent)
    assert agent.name == "cursor"


def test_agent_enabled_flag():
    agent = create_agent(AgentConfig(agent=AgentType.CODEX, enabled=False))
    assert agent.enabled is False


def test_all_agents_inherit_base():
    for agent_type in AgentType:
        agent = create_agent(AgentConfig(agent=agent_type))
        assert isinstance(agent, BaseAgent)

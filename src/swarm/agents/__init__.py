from swarm.config.schema import AgentConfig, AgentType

from .base import BaseAgent
from .claude_code import ClaudeCodeAgent
from .codex import CodexAgent
from .cursor import CursorAgent

AGENT_REGISTRY: dict[AgentType, type[BaseAgent]] = {
    AgentType.CLAUDE_CODE: ClaudeCodeAgent,
    AgentType.CODEX: CodexAgent,
    AgentType.CURSOR: CursorAgent,
}


def create_agent(config: AgentConfig, work_dir: str = ".") -> BaseAgent:
    """Factory: instantiate an agent adapter from config."""
    cls = AGENT_REGISTRY.get(config.agent)
    if cls is None:
        raise ValueError(f"Unknown agent type: {config.agent}")
    return cls(config, work_dir)


__all__ = [
    "AGENT_REGISTRY",
    "BaseAgent",
    "ClaudeCodeAgent",
    "CodexAgent",
    "CursorAgent",
    "create_agent",
]

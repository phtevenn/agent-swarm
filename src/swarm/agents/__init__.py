from swarm.config.schema import AgentConfig, AgentType, ApprovalMode

from .base import BaseAgent
from .claude_code import ClaudeCodeAgent
from .codex import CodexAgent
from .cursor import CursorAgent

AGENT_REGISTRY: dict[AgentType, type[BaseAgent]] = {
    AgentType.CLAUDE_CODE: ClaudeCodeAgent,
    AgentType.CODEX: CodexAgent,
    AgentType.CURSOR: CursorAgent,
}


def create_agent(
    config: AgentConfig,
    work_dir: str = ".",
    approval_mode: ApprovalMode = ApprovalMode.DEFAULT,
) -> BaseAgent:
    """Factory: instantiate an agent adapter from config.

    The approval_mode is set at the swarm level and inherited by every agent
    so that workers run with the same permissions as the lead.
    """
    cls = AGENT_REGISTRY.get(config.agent)
    if cls is None:
        raise ValueError(f"Unknown agent type: {config.agent}")
    return cls(config, work_dir, approval_mode=approval_mode)


__all__ = [
    "AGENT_REGISTRY",
    "BaseAgent",
    "ClaudeCodeAgent",
    "CodexAgent",
    "CursorAgent",
    "create_agent",
]

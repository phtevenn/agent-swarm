"""Tests for agent factory, registry, and permission inheritance."""

from swarm.agents import AGENT_REGISTRY, create_agent
from swarm.agents.base import BaseAgent
from swarm.agents.claude_code import ClaudeCodeAgent
from swarm.agents.codex import CodexAgent
from swarm.agents.cursor import CursorAgent
from swarm.agents.gemini import GeminiAgent
from swarm.config.schema import AgentConfig, AgentType, ApprovalMode


def test_registry_has_all_agents():
    assert AgentType.CLAUDE_CODE in AGENT_REGISTRY
    assert AgentType.CODEX in AGENT_REGISTRY
    assert AgentType.CURSOR in AGENT_REGISTRY
    assert AgentType.GEMINI in AGENT_REGISTRY


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


def test_create_gemini():
    agent = create_agent(AgentConfig(agent=AgentType.GEMINI))
    assert isinstance(agent, GeminiAgent)
    assert agent.name == "gemini"


def test_agent_enabled_flag():
    agent = create_agent(AgentConfig(agent=AgentType.CODEX, enabled=False))
    assert agent.enabled is False


def test_all_agents_inherit_base():
    for agent_type in AgentType:
        agent = create_agent(AgentConfig(agent=agent_type))
        assert isinstance(agent, BaseAgent)


# --- Permission inheritance ---


def test_approval_mode_propagated_to_agent():
    for agent_type in AgentType:
        agent = create_agent(
            AgentConfig(agent=agent_type),
            approval_mode=ApprovalMode.FULL_AUTO,
        )
        assert agent.approval_mode == ApprovalMode.FULL_AUTO


def test_default_approval_mode():
    agent = create_agent(AgentConfig(agent=AgentType.CLAUDE_CODE))
    assert agent.approval_mode == ApprovalMode.DEFAULT


def test_claude_code_full_auto_flags():
    agent = create_agent(
        AgentConfig(agent=AgentType.CLAUDE_CODE),
        approval_mode=ApprovalMode.FULL_AUTO,
    )
    cmd = agent._build_cmd()
    assert "--dangerously-skip-permissions" in cmd


def test_claude_code_suggest_flags():
    agent = create_agent(
        AgentConfig(agent=AgentType.CLAUDE_CODE),
        approval_mode=ApprovalMode.SUGGEST,
    )
    cmd = agent._build_cmd()
    assert "--permission-mode" in cmd
    idx = cmd.index("--permission-mode")
    assert cmd[idx + 1] == "plan"


def test_codex_full_auto_flags():
    agent = create_agent(
        AgentConfig(agent=AgentType.CODEX),
        approval_mode=ApprovalMode.FULL_AUTO,
    )
    cmd = agent._build_cmd()
    assert cmd[0] == "codex"
    assert cmd[1] == "exec"
    assert "--full-auto" in cmd


def test_codex_auto_edit_flags():
    agent = create_agent(
        AgentConfig(agent=AgentType.CODEX),
        approval_mode=ApprovalMode.AUTO_EDIT,
    )
    cmd = agent._build_cmd()
    assert "-a" in cmd
    idx = cmd.index("-a")
    assert cmd[idx + 1] == "on-request"
    assert "-s" in cmd
    idx = cmd.index("-s")
    assert cmd[idx + 1] == "workspace-write"


def test_codex_suggest_flags():
    agent = create_agent(
        AgentConfig(agent=AgentType.CODEX),
        approval_mode=ApprovalMode.SUGGEST,
    )
    cmd = agent._build_cmd()
    assert "-a" in cmd
    idx = cmd.index("-a")
    assert cmd[idx + 1] == "untrusted"
    assert "-s" in cmd
    idx = cmd.index("-s")
    assert cmd[idx + 1] == "read-only"


def test_cursor_full_auto_flags():
    agent = create_agent(
        AgentConfig(agent=AgentType.CURSOR),
        approval_mode=ApprovalMode.FULL_AUTO,
    )
    cmd = agent._build_cmd()
    assert "--yolo" in cmd
    assert "--trust" in cmd
    assert cmd[0] == "agent"


def test_cursor_suggest_flags():
    agent = create_agent(
        AgentConfig(agent=AgentType.CURSOR),
        approval_mode=ApprovalMode.SUGGEST,
    )
    cmd = agent._build_cmd()
    assert "--mode" in cmd
    idx = cmd.index("--mode")
    assert cmd[idx + 1] == "plan"


def test_cursor_uses_agent_binary():
    """Cursor adapter should use `agent` as the CLI command, not `cursor`."""
    agent = create_agent(AgentConfig(agent=AgentType.CURSOR))
    cmd = agent._build_cmd()
    assert cmd[0] == "agent"


def test_cursor_json_output_parsed_for_streaming():
    """Cursor JSON stdout is converted to readable result for streaming display."""
    agent = create_agent(AgentConfig(agent=AgentType.CURSOR))
    raw = '{"type":"result","subtype":"success","result":"Created script.\\nRun: python x.py"}'
    assert agent._line_to_readable(raw) == "Created script.\nRun: python x.py"
    # Non-JSON line is passed through
    assert agent._line_to_readable("plain text") == "plain text"
    # Invalid JSON is passed through
    assert agent._line_to_readable("{broken") == "{broken"


def test_gemini_full_auto_flags():
    """Gemini full-auto uses --yolo so headless auto-approves tool actions."""
    agent = create_agent(
        AgentConfig(agent=AgentType.GEMINI),
        approval_mode=ApprovalMode.FULL_AUTO,
    )
    cmd = agent._build_cmd()
    assert "gemini" in cmd
    assert "--output-format" in cmd
    assert "json" in cmd
    assert "--yolo" in cmd
    assert "--sandbox" not in cmd


def test_gemini_suggest_flags():
    """Gemini suggest mode uses --sandbox."""
    agent = create_agent(
        AgentConfig(agent=AgentType.GEMINI),
        approval_mode=ApprovalMode.SUGGEST,
    )
    cmd = agent._build_cmd()
    assert "--sandbox" in cmd


def test_gemini_uses_gemini_binary():
    """Gemini adapter uses `gemini` as the CLI command."""
    agent = create_agent(AgentConfig(agent=AgentType.GEMINI))
    cmd = agent._build_cmd()
    assert cmd[0] == "gemini"


def test_gemini_json_response_parsed():
    """Gemini headless JSON uses 'response' field."""
    agent = create_agent(AgentConfig(agent=AgentType.GEMINI))
    raw = '{"response":"Done.","stats":{"prompt_tokens":10}}'
    assert agent._extract_result(raw) == "Done."
    assert agent._line_to_readable(raw) == "Done."
    # Non-JSON passed through
    assert agent._extract_result("plain") == "plain"


def test_model_override_in_cmd():
    for agent_type in AgentType:
        agent = create_agent(AgentConfig(agent=agent_type, model="test-model"))
        cmd = agent._build_cmd()
        # Gemini uses -m, others use --model
        assert "--model" in cmd or "-m" in cmd
        flag = "--model" if "--model" in cmd else "-m"
        idx = cmd.index(flag)
        assert cmd[idx + 1] == "test-model"


# --- Session tracking ---


def test_session_not_started_initially():
    agent = create_agent(AgentConfig(agent=AgentType.CLAUDE_CODE))
    assert agent._session_started is False

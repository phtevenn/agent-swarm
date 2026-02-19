"""Rich rendering for agent responses.

Formats agent output similar to how Claude Code / other coding agents
display responses: markdown rendering with syntax-highlighted code blocks,
clean visual separation, and styled delegation status lines.
"""

from __future__ import annotations

import re

from rich.console import Console
from rich.markdown import Markdown
from rich.padding import Padding
from rich.rule import Rule

console = Console()

_WORKER_STYLE = "blue"
_SUCCESS_STYLE = "bold green"
_FAIL_STYLE = "bold red"
_DIM = "dim"

# Per-agent state to skip boilerplate when streaming worker output.
_worker_display_state: dict[str, dict] = {}

# Patterns to summarize common worker errors (so we don't dump huge stderr).
def _first_line_or_cap(s: str, cap: int = 120) -> str:
    first = s.split("\n")[0].strip()
    return first[:cap] + "..." if len(first) > cap else first


_SUMMARY_PATTERNS = [
    (re.compile(r"429|rateLimitExceeded|RESOURCE_EXHAUSTED|Too Many Requests", re.I), "Rate limit (429)"),
    (re.compile(r"No capacity available[^\n]*", re.I), lambda m: _first_line_or_cap(m.group(0))),
    (re.compile(r"Tool [\"']([^\"']+)[\"'] not found", re.I), "Tool not available in this mode (headless may have fewer tools)"),
    (re.compile(r"run_shell_command.*not found", re.I), "run_shell_command not available in headless mode"),
    (re.compile(r"produced no output for \d+s", re.I), lambda m: m.group(0)),
    (re.compile(r"Timed out after \d+s", re.I), lambda m: m.group(0)),
]


def _summarize_worker_error(raw: str, max_len: int = 200) -> str:
    """Turn a long stderr/exception into a short one-line summary."""
    if not raw or len(raw) <= max_len:
        return raw.strip()
    for pattern, repl in _SUMMARY_PATTERNS:
        m = pattern.search(raw)
        if m:
            if callable(repl):
                return repl(m)
            return repl
    return raw.strip()[:max_len] + "..."


def render_response(text: str, agent_name: str = "") -> None:
    """Render an agent's response as formatted markdown."""
    console.print()
    md = Markdown(text, code_theme="monokai")
    console.print(Padding(md, (0, 2)))
    console.print()


def render_delegation_header(text: str) -> None:
    """Render lead agent text that precedes a delegation block."""
    if not text.strip():
        return
    console.print()
    md = Markdown(text, code_theme="monokai")
    console.print(Padding(md, (0, 2)))


def render_delegation_start(tasks: list[dict]) -> None:
    """Show a summary of tasks being delegated."""
    console.print()
    console.print(Rule("[bold]Delegating to workers[/bold]", style=_DIM))
    for req in tasks:
        agent = req.get("agent", "?")
        task = req.get("task", "?")
        console.print(f"  [{_WORKER_STYLE}]{agent}[/] → {task}")
    console.print()


def render_worker_start(agent_name: str, task: str) -> None:
    """Show a worker starting a task."""
    _worker_display_state[agent_name] = {"started": False}
    console.print(f"  [bold blue]▶[/bold blue] [{_WORKER_STYLE}]{agent_name}[/]  {task}")


def _is_worker_boilerplate(line: str) -> bool:
    """True if this line is CLI boilerplate we should not show (Output:, code fences, etc.)."""
    s = line.strip()
    if s == "Output:" or s == "Output":
        return True
    if s == "```" or (s.startswith("```") and re.match(r"^```[a-z0-9]*\s*$", s)):
        return True
    return False


def render_worker_line(agent_name: str, text: str) -> None:
    """Render a single line of streaming output from a worker, skipping boilerplate."""
    state = _worker_display_state.setdefault(agent_name, {"started": False})
    if _is_worker_boilerplate(text):
        return
    if not text.strip() and not state["started"]:
        return
    state["started"] = True
    console.print(f"  [{_DIM}]{agent_name}[/] │ {text}")


def render_worker_done(agent_name: str) -> None:
    """Show a worker completing a task."""
    console.print(f"  [{_SUCCESS_STYLE}]✓[/] [{_WORKER_STYLE}]{agent_name}[/]  done")


def render_worker_fail(agent_name: str, error: str) -> None:
    """Show a worker failing a task. Long errors are summarized to one line."""
    summary = _summarize_worker_error(error)
    console.print(f"  [{_FAIL_STYLE}]✗[/] [{_WORKER_STYLE}]{agent_name}[/]  {summary}")


def render_worker_feedback_request(agent_name: str, question: str) -> None:
    """Show that a worker is asking the lead for feedback."""
    console.print(
        f"  [bold yellow]↩[/] [{_WORKER_STYLE}]{agent_name}[/] requests feedback: [dim]{question}[/]"
    )
    console.print("  [dim]Asking lead for guidance…[/]")


def render_delegation_end() -> None:
    """Visual separator after delegation results are collected."""
    console.print()
    console.print(Rule("[bold]Workers finished — synthesizing[/bold]", style=_DIM))
    console.print()


def render_error(message: str) -> None:
    """Render an error message."""
    console.print(f"\n  [bold red]Error:[/bold red] {message}\n")

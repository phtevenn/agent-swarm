"""Rich rendering for agent responses.

Formats agent output similar to how Claude Code / other coding agents
display responses: markdown rendering with syntax-highlighted code blocks,
clean visual separation, and styled delegation status lines.
"""

from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown
from rich.padding import Padding
from rich.rule import Rule
from rich.text import Text

console = Console()

_LEAD_STYLE = "cyan"
_WORKER_STYLE = "blue"
_SUCCESS_STYLE = "bold green"
_FAIL_STYLE = "bold red"
_DIM = "dim"


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
    console.print(f"  [bold blue]▶[/bold blue] [{_WORKER_STYLE}]{agent_name}[/]  {task}")


def render_worker_done(agent_name: str) -> None:
    """Show a worker completing a task."""
    console.print(f"  [{_SUCCESS_STYLE}]✓[/] [{_WORKER_STYLE}]{agent_name}[/]  done")


def render_worker_fail(agent_name: str, error: str) -> None:
    """Show a worker failing a task."""
    console.print(f"  [{_FAIL_STYLE}]✗[/] [{_WORKER_STYLE}]{agent_name}[/]  {error}")


def render_delegation_end() -> None:
    """Visual separator after delegation results are collected."""
    console.print()
    console.print(Rule("[bold]Workers finished — synthesizing[/bold]", style=_DIM))
    console.print()


def render_error(message: str) -> None:
    """Render an error message."""
    console.print(f"\n  [bold red]Error:[/bold red] {message}\n")

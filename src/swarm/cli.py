"""CLI entry point for Agent Swarm.

Usage:
    swarm                              Start interactive session in cwd
    swarm -p "do something"            One-shot task, then exit
    swarm status                       Show agent status table
    swarm check                        Health-check all agent CLIs
    swarm trust                        Trust the current workspace
    swarm trust --revoke               Revoke trust for current workspace
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from swarm.agents import create_agent
from swarm.config import load_config, load_config_with_fallback
from swarm.config.schema import Config
from swarm.core import Orchestrator
from swarm.core.render import render_error, render_response
from swarm.core.trust import (
    is_workspace_trusted,
    requires_trust,
    revoke_trust,
    trust_workspace,
)

console = Console()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _load_or_exit(config_path: str | None) -> tuple[Config, str]:
    """Load config with fallback to defaults. Returns (config, source)."""
    try:
        return load_config_with_fallback(config_path)
    except FileNotFoundError:
        console.print(f"[bold red]Error:[/] Config not found: {config_path}")
        sys.exit(1)


def _build_orchestrator(config: Config, work_dir: str = ".") -> Orchestrator:
    mode = config.swarm.approval_mode
    lead = create_agent(config.swarm.lead, work_dir=work_dir, approval_mode=mode)
    workers = [
        create_agent(wc, work_dir=work_dir, approval_mode=mode)
        for wc in config.swarm.workers
        if wc.enabled
    ]
    return Orchestrator(config, lead, workers)


def _check_trust(config: Config, trust_flag: bool) -> bool:
    """Verify workspace trust. Returns True if safe to proceed."""
    mode = config.swarm.approval_mode
    if not requires_trust(mode):
        return True

    workspace = Path.cwd()
    if trust_flag or is_workspace_trusted(workspace):
        return True

    console.print(
        Panel(
            f"[bold yellow]Workspace not trusted[/]\n\n"
            f"  Directory: [cyan]{workspace}[/]\n"
            f"  Approval mode: [bold red]{mode.value}[/]\n\n"
            f"Swarm will spawn agents with elevated permissions in this directory.\n"
            f"Each agent's individual trust check is bypassed by the swarm.\n\n"
            f"[dim]To trust this workspace permanently, run:[/]\n"
            f"  [green]swarm trust[/]\n\n"
            f"[dim]Or start with --trust to trust for this session only:[/]\n"
            f"  [green]swarm --trust[/]",
            title="Trust Required",
            border_style="yellow",
        )
    )
    return False


def _print_banner(config: Config, config_source: str) -> None:
    mode = config.swarm.approval_mode.value
    lead_name = config.swarm.lead.agent.value
    worker_names = [w.agent.value for w in config.swarm.workers if w.enabled]
    workers_str = ", ".join(worker_names) if worker_names else "(none)"
    workspace = Path.cwd()

    console.print(
        Panel(
            f"  [dim]Workspace:[/]  {workspace}\n"
            f"  [dim]Config:[/]     {config_source}\n"
            f"  [dim]Lead:[/]       [bold cyan]{lead_name}[/]\n"
            f"  [dim]Workers:[/]    {workers_str}\n"
            f"  [dim]Approval:[/]   [bold yellow]{mode}[/]",
            title="[bold]Agent Swarm[/]",
            border_style="blue",
            padding=(1, 2),
        )
    )


# ---------------------------------------------------------------------------
# Async REPL — supports Ctrl+C to interrupt running agents
# ---------------------------------------------------------------------------


async def _async_input(prompt_text: str) -> str:
    """Read a line of input without blocking the event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: console.input(prompt_text))


async def _run_chat(orch: Orchestrator, message: str) -> None:
    """Run a chat message through the orchestrator with cancellation support."""
    response = await orch.chat(message)
    if response is not None:
        render_response(response, agent_name=orch.lead.name)


async def _async_interactive_loop(orch: Orchestrator) -> None:
    """Async REPL: Ctrl+C interrupts the running agent, not the session."""
    console.print("[dim]Talk to the lead agent, or /help for commands. Ctrl+C to interrupt.[/]\n")

    current_task: asyncio.Task | None = None

    loop = asyncio.get_running_loop()
    interrupted = asyncio.Event()

    original_sigint = signal.getsignal(signal.SIGINT)

    def _handle_sigint(*_: object) -> None:
        if current_task and not current_task.done():
            current_task.cancel()
            interrupted.set()
        else:
            signal.signal(signal.SIGINT, original_sigint)
            loop.call_soon(lambda: None)

    while True:
        signal.signal(signal.SIGINT, original_sigint)
        interrupted.clear()

        try:
            message = await _async_input("[bold green]swarm>[/] ")
            message = message.strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye.[/]")
            break

        if not message:
            continue

        if message.startswith("/"):
            if await _handle_command(message, orch):
                break
            continue

        signal.signal(signal.SIGINT, _handle_sigint)

        current_task = asyncio.create_task(_run_chat(orch, message))
        try:
            await current_task
        except asyncio.CancelledError:
            console.print("\n[yellow]Interrupted — agents cancelled.[/]\n")
            await orch.cancel_all()
        except Exception as exc:
            render_error(str(exc))
        finally:
            current_task = None

    signal.signal(signal.SIGINT, original_sigint)


def _interactive_loop(orch: Orchestrator) -> None:
    """Entry point for the interactive REPL."""
    asyncio.run(_async_interactive_loop(orch))


async def _handle_command(cmd: str, orch: Orchestrator) -> bool:
    """Handle /slash commands. Returns True if the session should end."""
    parts = cmd.split()
    name = parts[0].lower()

    if name in ("/quit", "/exit", "/q"):
        console.print("[dim]Goodbye.[/]")
        return True

    if name == "/status":
        await _print_status_table(orch)
        return False

    if name == "/check":
        await _run_health_checks(orch)
        return False

    if name == "/help":
        console.print(
            "[bold]Commands:[/]\n"
            "  [cyan]/status[/]  — Show agent status\n"
            "  [cyan]/check[/]   — Health-check agent CLIs\n"
            "  [cyan]/help[/]    — Show this help\n"
            "  [cyan]/quit[/]    — Exit swarm\n"
            "\n"
            "[dim]Ctrl+C interrupts the running agent without exiting.[/]\n"
        )
        return False

    console.print(f"[yellow]Unknown command: {name}. Type /help for options.[/]")
    return False


async def _print_status_table(orch: Orchestrator) -> None:
    mode = orch.config.swarm.approval_mode.value
    table = Table(title=f"Agent Status  [dim](approval: {mode})[/dim]")
    table.add_column("Agent", style="cyan")
    table.add_column("Role", style="magenta")
    table.add_column("Enabled", style="green")
    table.add_column("Approval", style="yellow")
    table.add_column("State")

    statuses = await orch.get_status()
    table.add_row(
        orch.lead.name,
        "lead",
        "✓" if orch.lead.enabled else "✗",
        mode,
        statuses.get(orch.lead.name, {}).get("state", "idle"),
    )
    for name, agent in orch.workers.items():
        table.add_row(
            name,
            "worker",
            "✓" if agent.enabled else "✗",
            mode,
            statuses.get(name, {}).get("state", "idle"),
        )
    console.print(table)


async def _run_health_checks(orch: Orchestrator) -> None:
    console.print("[bold]Health checks:[/]")
    for name, agent in orch.all_agents.items():
        ok = await agent.health_check()
        icon = "[bold green]✓[/]" if ok else "[bold red]✗[/]"
        console.print(f"  {icon} {name}")


# ---------------------------------------------------------------------------
# Click CLI
# ---------------------------------------------------------------------------


@click.group(invoke_without_command=True)
@click.option("-p", "--prompt", default=None, help="One-shot task prompt (non-interactive).")
@click.option("--config", default=None, help="Path to swarm configuration file.")
@click.option("--trust", "trust_flag", is_flag=True, help="Trust this workspace for the session.")
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging.")
@click.pass_context
def main(
    ctx: click.Context,
    prompt: str | None,
    config: str | None,
    trust_flag: bool,
    verbose: bool,
) -> None:
    """Agent Swarm — orchestrate multiple coding agents.

    \b
    cd into a repo and run:
        swarm                          interactive session
        swarm -p "refactor auth"       one-shot task
        swarm status                   show agent table
        swarm check                    health-check CLIs
        swarm trust                    trust this workspace
    """
    _setup_logging(verbose)
    ctx.ensure_object(dict)

    ctx.obj["config_explicit"] = config
    ctx.obj["trust_flag"] = trust_flag

    if ctx.invoked_subcommand is not None:
        return

    cfg, source = _load_or_exit(config)

    if not _check_trust(cfg, trust_flag):
        sys.exit(1)

    orch = _build_orchestrator(cfg, work_dir=str(Path.cwd()))
    _print_banner(cfg, source)

    if prompt:
        try:
            response = asyncio.run(orch.chat(prompt))
            if response is not None:
                render_response(response, agent_name=orch.lead.name)
        except Exception as exc:
            render_error(str(exc))
            sys.exit(1)
    else:
        _interactive_loop(orch)


@main.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show status of configured agents."""
    cfg, _source = _load_or_exit(ctx.obj["config_explicit"])
    orch = _build_orchestrator(cfg)
    asyncio.run(_print_status_table(orch))


@main.command()
@click.pass_context
def check(ctx: click.Context) -> None:
    """Run health checks on all configured agents."""
    cfg, _source = _load_or_exit(ctx.obj["config_explicit"])
    orch = _build_orchestrator(cfg)
    asyncio.run(_run_health_checks(orch))


@main.command("trust")
@click.option("--revoke", is_flag=True, help="Revoke trust for the current workspace.")
def trust_cmd(revoke: bool) -> None:
    """Trust or revoke trust for the current workspace."""
    workspace = Path.cwd()
    if revoke:
        if revoke_trust(workspace):
            console.print(f"[yellow]Revoked trust for:[/] {workspace}")
        else:
            console.print(f"[dim]Workspace was not trusted:[/] {workspace}")
    else:
        trust_workspace(workspace)
        console.print(f"[green]Trusted workspace:[/] {workspace}")


if __name__ == "__main__":
    main()

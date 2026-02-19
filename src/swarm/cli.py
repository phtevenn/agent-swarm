"""CLI entry point for Agent Swarm."""

from __future__ import annotations

import asyncio
import logging
import sys

import click
from rich.console import Console
from rich.table import Table

from swarm.agents import create_agent
from swarm.config import load_config
from swarm.core import Orchestrator

console = Console()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _build_orchestrator(config_path: str) -> Orchestrator:
    config = load_config(config_path)
    lead = create_agent(config.swarm.lead)
    workers = [
        create_agent(wc)
        for wc in config.swarm.workers
        if wc.enabled
    ]
    return Orchestrator(config, lead, workers)


@click.group()
@click.option("--config", default="config/swarm.yaml", help="Path to swarm configuration file.")
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging.")
@click.pass_context
def main(ctx: click.Context, config: str, verbose: bool) -> None:
    """Agent Swarm — orchestrate multiple coding agents."""
    _setup_logging(verbose)
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config


@main.command()
@click.argument("task")
@click.pass_context
def run(ctx: click.Context, task: str) -> None:
    """Submit a task to the swarm."""
    try:
        orch = _build_orchestrator(ctx.obj["config_path"])
    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/] {e}")
        sys.exit(1)

    console.print(f"\n[bold]Agent Swarm[/] — submitting task\n")
    result = asyncio.run(orch.run_task(task))
    console.print(f"\n[bold green]Result:[/]\n{result}")


@main.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show status of configured agents."""
    try:
        orch = _build_orchestrator(ctx.obj["config_path"])
    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/] {e}")
        sys.exit(1)

    table = Table(title="Agent Status")
    table.add_column("Agent", style="cyan")
    table.add_column("Role", style="magenta")
    table.add_column("Enabled", style="green")
    table.add_column("State")

    statuses = asyncio.run(orch.get_status())
    table.add_row(
        orch.lead.name,
        "lead",
        "✓" if orch.lead.enabled else "✗",
        statuses.get(orch.lead.name, {}).get("state", "idle"),
    )
    for name, agent in orch.workers.items():
        table.add_row(
            name,
            "worker",
            "✓" if agent.enabled else "✗",
            statuses.get(name, {}).get("state", "idle"),
        )

    console.print(table)


@main.command()
@click.pass_context
def check(ctx: click.Context) -> None:
    """Run health checks on all configured agents."""
    try:
        orch = _build_orchestrator(ctx.obj["config_path"])
    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/] {e}")
        sys.exit(1)

    async def _check() -> None:
        for name, agent in orch.all_agents.items():
            ok = await agent.health_check()
            icon = "[bold green]✓[/]" if ok else "[bold red]✗[/]"
            console.print(f"  {icon} {name}")

    console.print("[bold]Health checks:[/]")
    asyncio.run(_check())


if __name__ == "__main__":
    main()

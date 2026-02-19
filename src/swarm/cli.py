"""CLI entry point for Agent Swarm."""

import click


@click.group()
@click.option("--config", default="config/swarm.yaml", help="Path to swarm configuration file.")
@click.pass_context
def main(ctx: click.Context, config: str) -> None:
    """Agent Swarm — orchestrate multiple coding agents."""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config


@main.command()
@click.argument("task")
@click.pass_context
def run(ctx: click.Context, task: str) -> None:
    """Submit a task to the swarm."""
    click.echo(f"[swarm] Task received: {task}")
    click.echo("[swarm] Not yet implemented — see Phase 1 roadmap.")


@main.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show status of running agents."""
    click.echo("[swarm] Status: no agents running.")


if __name__ == "__main__":
    main()

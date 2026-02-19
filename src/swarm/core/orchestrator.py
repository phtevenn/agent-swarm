"""Core orchestrator — coordinates the lead agent and worker agents."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from rich.console import Console

from .message_bus import MessageBus
from .task import Task, TaskStatus

if TYPE_CHECKING:
    from swarm.agents.base import BaseAgent
    from swarm.config.schema import Config

logger = logging.getLogger(__name__)
console = Console()


class Orchestrator:
    """Manages agent lifecycle and task delegation.

    Flow:
    1. Human submits a top-level task via CLI
    2. Lead agent decomposes it into subtasks
    3. Orchestrator assigns subtasks to available workers
    4. Workers execute and report back through the message bus
    5. Lead agent synthesizes results
    """

    def __init__(self, config: Config, lead: BaseAgent, workers: list[BaseAgent]) -> None:
        self.config = config
        self.lead = lead
        self.workers = {w.name: w for w in workers}
        self.bus = MessageBus(config.swarm.bus_dir)
        self._active_tasks: dict[str, asyncio.Task] = {}

    @property
    def all_agents(self) -> dict[str, BaseAgent]:
        return {self.lead.name: self.lead, **self.workers}

    async def run_task(self, prompt: str) -> str:
        """Execute a full orchestration cycle for a human-submitted task."""
        root_task = Task(title=prompt, created_by="human")
        self.bus.publish_task(root_task)

        console.print(f"[bold green]Task created:[/] {root_task.id}")
        console.print(f"[dim]Lead agent:[/] {self.lead.name}")

        subtasks = await self._decompose(root_task)

        if not subtasks:
            console.print("[yellow]Lead agent returned no subtasks — executing directly.[/]")
            return await self._execute_single(root_task)

        results = await self._execute_parallel(subtasks)

        synthesis = await self._synthesize(root_task, results)
        root_task.complete(synthesis)
        self.bus.publish_task(root_task)
        return synthesis

    async def _decompose(self, root_task: Task) -> list[Task]:
        """Ask the lead agent to break a task into subtasks."""
        console.print("[bold]Decomposing task...[/]")
        decomposition = await self.lead.decompose(root_task.title)

        subtasks = []
        available_workers = [n for n, w in self.workers.items() if w.enabled]

        for i, item in enumerate(decomposition):
            worker_name = available_workers[i % len(available_workers)] if available_workers else self.lead.name
            subtask = Task(
                parent_id=root_task.id,
                title=item["title"],
                description=item.get("description", ""),
                created_by=self.lead.name,
            )
            subtask.assign(worker_name)
            self.bus.publish_task(subtask)
            subtasks.append(subtask)
            console.print(f"  [cyan]→ {subtask.id}[/] [{worker_name}] {subtask.title}")

        return subtasks

    async def _execute_single(self, task: Task) -> str:
        """Execute a task directly with the lead agent (no decomposition)."""
        task.start()
        self.bus.publish_task(task)
        result = await self.lead.execute(task.title, task.description)
        task.complete(result)
        self.bus.publish_task(task)
        return result

    async def _execute_parallel(self, subtasks: list[Task]) -> dict[str, str]:
        """Run subtasks on their assigned workers, respecting max_parallel."""
        sem = asyncio.Semaphore(self.config.swarm.tasks.max_parallel)
        results: dict[str, str] = {}

        async def _run(subtask: Task) -> None:
            async with sem:
                agent_name = subtask.assigned_to
                agent = self.all_agents.get(agent_name)
                if agent is None:
                    subtask.fail(f"No agent found with name '{agent_name}'")
                    self.bus.publish_task(subtask)
                    return

                subtask.start()
                self.bus.publish_task(subtask)
                self.bus.update_status(agent_name, {
                    "state": "working",
                    "task_id": subtask.id,
                })
                console.print(f"  [bold blue]▶[/] {agent_name} starting: {subtask.title}")

                try:
                    timeout = self.config.swarm.tasks.worker_timeout
                    result = await asyncio.wait_for(
                        agent.execute(subtask.title, subtask.description),
                        timeout=timeout,
                    )
                    subtask.complete(result)
                    results[subtask.id] = result
                    console.print(f"  [bold green]✓[/] {agent_name} completed: {subtask.title}")
                except asyncio.TimeoutError:
                    subtask.fail(f"Timed out after {timeout}s")
                    console.print(f"  [bold red]✗[/] {agent_name} timed out: {subtask.title}")
                except Exception as exc:
                    subtask.fail(str(exc))
                    console.print(f"  [bold red]✗[/] {agent_name} failed: {exc}")
                finally:
                    self.bus.publish_task(subtask)
                    self.bus.update_status(agent_name, {"state": "idle"})

        await asyncio.gather(*[_run(st) for st in subtasks])
        return results

    async def _synthesize(self, root_task: Task, results: dict[str, str]) -> str:
        """Ask the lead agent to synthesize subtask results."""
        console.print("[bold]Synthesizing results...[/]")
        return await self.lead.synthesize(root_task.title, results)

    async def get_status(self) -> dict:
        """Return current status of all agents."""
        statuses = {}
        for name in self.all_agents:
            s = self.bus.read_status(name)
            statuses[name] = s if s else {"state": "idle"}
        return statuses

    async def cancel_all(self) -> None:
        """Cancel all running tasks."""
        for task_id, async_task in self._active_tasks.items():
            async_task.cancel()
            logger.info("Cancelled async task for %s", task_id)
        self._active_tasks.clear()

        for task in self.bus.list_tasks():
            if task.status in (TaskStatus.PENDING, TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS):
                task.cancel()
                self.bus.publish_task(task)

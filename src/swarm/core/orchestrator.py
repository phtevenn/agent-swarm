"""Core orchestrator — the lead agent is conversational and decides delegation.

The human talks to the lead agent like any other coding agent. The lead has a
system prompt describing its available workers and a delegation protocol. When
the lead wants to fan out work, it emits <swarm:delegate> blocks. The
orchestrator intercepts those, runs the tasks on workers, and feeds results
back to the lead.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import TYPE_CHECKING

from . import render
from .message_bus import MessageBus
from .task import Task, TaskStatus

if TYPE_CHECKING:
    from swarm.agents.base import BaseAgent
    from swarm.config.schema import Config

logger = logging.getLogger(__name__)

DELEGATE_PATTERN = re.compile(
    r"<swarm:delegate>\s*(.*?)\s*</swarm:delegate>",
    re.DOTALL,
)


def _build_system_prompt(workers: dict[str, BaseAgent]) -> str:
    """Build the system prompt that tells the lead about its delegation powers."""
    if not workers:
        return ""

    worker_lines = []
    for name, agent in workers.items():
        if agent.enabled:
            worker_lines.append(f"  - {name}")

    workers_list = "\n".join(worker_lines)

    return (
        "You are the lead agent in a coding agent swarm. You have worker agents "
        "available that you can delegate tasks to. You should work like a normal "
        "coding agent — answer questions, write code, make edits directly. "
        "Delegation is optional; use it when:\n"
        "  - The task is large and can be parallelized\n"
        "  - The user explicitly asks you to delegate\n"
        "  - Different subtasks are independent and would benefit from parallel execution\n"
        "\n"
        "Available workers:\n"
        f"{workers_list}\n"
        "\n"
        "To delegate, include a block like this in your response:\n"
        "\n"
        "<swarm:delegate>\n"
        '[{"agent": "worker-name", "task": "description of what to do"}]\n'
        "</swarm:delegate>\n"
        "\n"
        "You can include multiple tasks in the array. Any text outside the delegate "
        "block is shown to the user normally. After delegation completes, you will "
        "receive the results and can respond to the user.\n"
        "\n"
        "If delegation is unnecessary, just respond normally without any delegate block."
    )


class Orchestrator:
    """Manages conversational interaction with the lead and delegation to workers.

    The lead agent is the primary interface — the human talks to it directly.
    The orchestrator intercepts delegation requests and manages worker execution.
    """

    def __init__(self, config: Config, lead: BaseAgent, workers: list[BaseAgent]) -> None:
        self.config = config
        self.lead = lead
        self.workers = {w.name: w for w in workers}
        self.bus = MessageBus(config.swarm.bus_dir)
        self._system_prompt = _build_system_prompt(self.workers)
        self._active_tasks: dict[str, asyncio.Task] = {}

    @property
    def all_agents(self) -> dict[str, BaseAgent]:
        return {self.lead.name: self.lead, **self.workers}

    async def chat(self, message: str) -> str:
        """Send a message to the lead agent and handle any delegation.

        This is the main entry point. The lead responds conversationally.
        If its response contains <swarm:delegate> blocks, the orchestrator
        runs those tasks on workers and feeds results back to the lead.
        """
        response = await self.lead.send(
            message,
            system_prompt=self._system_prompt or None,
            continue_session=True,
        )

        delegation_match = DELEGATE_PATTERN.search(response)
        if not delegation_match:
            return response

        user_text = DELEGATE_PATTERN.sub("", response).strip()
        render.render_delegation_header(user_text)

        delegation_json = delegation_match.group(1)
        try:
            delegation_requests = json.loads(delegation_json)
        except json.JSONDecodeError:
            logger.warning("Lead emitted malformed delegation block, treating as plain text")
            return response

        render.render_delegation_start(delegation_requests)
        results = await self._run_delegations(delegation_requests)
        render.render_delegation_end()

        results_summary = "\n\n".join(
            f"## Worker: {r['agent']}\n### Task: {r['task']}\n### Result:\n{r['result']}"
            for r in results
        )
        followup = (
            f"The following delegated tasks have completed:\n\n{results_summary}\n\n"
            "Please review the results and provide a summary to the user."
        )

        return await self.lead.send(followup, continue_session=True)

    async def _run_delegations(self, requests: list[dict]) -> list[dict]:
        """Execute delegation requests on worker agents in parallel."""
        sem = asyncio.Semaphore(self.config.swarm.tasks.max_parallel)
        results: list[dict] = []

        async def _run_one(req: dict) -> dict:
            async with sem:
                agent_name = req.get("agent", "")
                task_desc = req.get("task", "")
                agent = self.workers.get(agent_name)

                task = Task(title=task_desc, assigned_to=agent_name, created_by=self.lead.name)
                task.assign(agent_name)
                self.bus.publish_task(task)

                if agent is None or not agent.enabled:
                    error = f"Worker '{agent_name}' not available"
                    task.fail(error)
                    self.bus.publish_task(task)
                    render.render_worker_fail(agent_name, error)
                    return {"agent": agent_name, "task": task_desc, "result": error}

                task.start()
                self.bus.publish_task(task)
                self.bus.update_status(agent_name, {"state": "working", "task_id": task.id})
                render.render_worker_start(agent_name, task_desc)

                try:
                    timeout = self.config.swarm.tasks.worker_timeout
                    result = await asyncio.wait_for(
                        agent.execute(task_desc),
                        timeout=timeout,
                    )
                    task.complete(result)
                    render.render_worker_done(agent_name)
                    return {"agent": agent_name, "task": task_desc, "result": result}
                except asyncio.TimeoutError:
                    error = f"Timed out after {timeout}s"
                    task.fail(error)
                    render.render_worker_fail(agent_name, error)
                    return {"agent": agent_name, "task": task_desc, "result": error}
                except Exception as exc:
                    task.fail(str(exc))
                    render.render_worker_fail(agent_name, str(exc))
                    return {"agent": agent_name, "task": task_desc, "result": str(exc)}
                finally:
                    self.bus.publish_task(task)
                    self.bus.update_status(agent_name, {"state": "idle"})

        completed = await asyncio.gather(*[_run_one(req) for req in requests])
        results.extend(completed)
        return results

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

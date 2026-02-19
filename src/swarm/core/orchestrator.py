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

from swarm.agents.base import WorkerNeedsFeedback

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
NEED_FEEDBACK_PATTERN = re.compile(
    r"<swarm:need-feedback>\s*(.*?)\s*</swarm:need-feedback>",
    re.DOTALL,
)

# Failure kinds the lead can act on (re-delegate or do themselves).
FAILURE_KIND_RATE_LIMIT = "rate_limit"
FAILURE_KIND_CAPACITY = "capacity"
FAILURE_KIND_TIMEOUT = "timeout"
FAILURE_KIND_NO_OUTPUT = "no_output"
FAILURE_KIND_TOOL_UNAVAILABLE = "tool_unavailable"
FAILURE_KIND_ERROR = "error"

_FAILURE_CLASSIFY = [
    (re.compile(r"429|rateLimitExceeded|Too Many Requests", re.I), FAILURE_KIND_RATE_LIMIT),
    (re.compile(r"RESOURCE_EXHAUSTED|No capacity available|MODEL_CAPACITY_EXHAUSTED", re.I), FAILURE_KIND_CAPACITY),
    (re.compile(r"Timed out after \d+s", re.I), FAILURE_KIND_TIMEOUT),
    (re.compile(r"produced no output for \d+s", re.I), FAILURE_KIND_NO_OUTPUT),
    (re.compile(r"run_shell_command.*not found|Tool .* not found", re.I), FAILURE_KIND_TOOL_UNAVAILABLE),
]


def _classify_failure(error_message: str) -> str | None:
    """Return a failure kind if the error is a known retriable/actionable type."""
    if not error_message:
        return None
    for pattern, kind in _FAILURE_CLASSIFY:
        if pattern.search(error_message):
            return kind
    return FAILURE_KIND_ERROR


def _build_results_summary(results: list[dict]) -> str:
    """Format delegation results for the lead, with FAILED status when applicable."""
    parts = []
    for r in results:
        agent = r.get("agent", "?")
        task = r.get("task", "?")
        result = r.get("result", "")
        status = r.get("status", "ok")
        failure_kind = r.get("failure_kind")
        if status == "failed" and failure_kind:
            parts.append(
                f"## Worker: {agent}\n"
                f"### Task: {task}\n"
                f"### Status: **FAILED** ({failure_kind})\n"
                f"### Result:\n{result}"
            )
        else:
            parts.append(
                f"## Worker: {agent}\n### Task: {task}\n### Result:\n{result}"
            )
    return "\n\n".join(parts)


def _build_followup(results: list[dict], round_index: int = 0) -> str:
    """Build the followup message to the lead; add re-delegate instructions if any failed."""
    summary = _build_results_summary(results)
    failed = [r for r in results if r.get("status") == "failed"]
    if failed:
        instruction = (
            "One or more tasks **failed** (e.g. rate limit or capacity). "
            "You may re-delegate the failed task(s) to a different worker by including "
            "a new <swarm:delegate> block with the same task assigned to another agent, "
            "or complete the task(s) yourself in your response."
        )
        if round_index > 0:
            instruction = "[Re-delegation round] " + instruction
    else:
        instruction = "Please review the results and provide a summary to the user."
    return f"The following delegated tasks have completed:\n\n{summary}\n\n{instruction}"


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
        "Workers can ask you for feedback mid-task by outputting:\n"
        "<swarm:need-feedback>their question</swarm:need-feedback>\n"
        "When that happens you will be asked to provide a short guidance reply; "
        "the worker will then be re-run with your feedback. Reply concisely.\n"
        "\n"
        "When a worker fails (e.g. rate limit, capacity, or timeout), you will see "
        "their result marked as FAILED with a reason. You can then either:\n"
        "  (1) Re-delegate the same task to a different worker by including a new "
        "<swarm:delegate> block that assigns the task to another agent (e.g. codex or cursor),\n"
        "  (2) Or complete the task yourself in your response.\n"
        "Prefer re-delegating to another worker when the failure is due to rate limits or capacity.\n"
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

    async def chat(self, message: str) -> str | None:
        """Send a message to the lead agent and handle any delegation.

        Returns the response text for the CLI to render, or None if the
        orchestrator already rendered everything (delegation flow).
        """
        lead_timeout = self.config.swarm.tasks.lead_timeout
        response = await asyncio.wait_for(
            self.lead.send(
                message,
                system_prompt=self._system_prompt or None,
                continue_session=True,
            ),
            timeout=lead_timeout,
        )

        max_delegate_rounds = 5
        round_index = 0

        while DELEGATE_PATTERN.search(response) and round_index < max_delegate_rounds:
            delegation_match = DELEGATE_PATTERN.search(response)
            if not delegation_match:
                break

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

            followup = _build_followup(results, round_index=round_index)
            response = await asyncio.wait_for(
                self.lead.send(followup, continue_session=True),
                timeout=lead_timeout,
            )
            round_index += 1

        render.render_response(response)
        return None

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
                    return {
                        "agent": agent_name,
                        "task": task_desc,
                        "result": error,
                        "status": "failed",
                        "failure_kind": FAILURE_KIND_ERROR,
                    }

                task.start()
                self.bus.publish_task(task)
                self.bus.update_status(agent_name, {"state": "working", "task_id": task.id})
                render.render_worker_start(agent_name, task_desc)

                try:
                    timeout = self.config.swarm.tasks.worker_timeout
                    no_output_timeout = self.config.swarm.tasks.no_output_timeout
                    lead_timeout = self.config.swarm.tasks.lead_timeout

                    def _on_line(text: str):
                        m = NEED_FEEDBACK_PATTERN.search(text)
                        if m:
                            return {"stop": True, "question": m.group(1).strip()}
                        render.render_worker_line(agent_name, text)
                        return None

                    result = await self._run_worker_with_feedback(
                        agent=agent,
                        agent_name=agent_name,
                        task_desc=task_desc,
                        task=task,
                        timeout=timeout,
                        no_output_timeout=no_output_timeout,
                        lead_timeout=lead_timeout,
                        on_line=_on_line,
                    )
                    task.complete(result)
                    render.render_worker_done(agent_name)
                    return {"agent": agent_name, "task": task_desc, "result": result, "status": "ok"}
                except asyncio.TimeoutError:
                    error = f"Timed out after {timeout}s"
                    task.fail(error)
                    render.render_worker_fail(agent_name, error)
                    kind = _classify_failure(error)
                    return {
                        "agent": agent_name,
                        "task": task_desc,
                        "result": error,
                        "status": "failed",
                        "failure_kind": kind,
                    }
                except Exception as exc:
                    err_str = str(exc)
                    task.fail(err_str)
                    render.render_worker_fail(agent_name, err_str)
                    kind = _classify_failure(err_str)
                    return {
                        "agent": agent_name,
                        "task": task_desc,
                        "result": err_str,
                        "status": "failed",
                        "failure_kind": kind or FAILURE_KIND_ERROR,
                    }
                finally:
                    self.bus.publish_task(task)
                    self.bus.update_status(agent_name, {"state": "idle"})

        completed = await asyncio.gather(*[_run_one(req) for req in requests])
        results.extend(completed)
        return results

    async def _run_worker_with_feedback(
        self,
        agent: BaseAgent,
        agent_name: str,
        task_desc: str,
        task: Task,
        timeout: int,
        no_output_timeout: int,
        lead_timeout: int,
        on_line,
        *,
        _feedback_round: int = 0,
    ) -> str:
        """Run worker; if it raises WorkerNeedsFeedback, ask lead and re-run once with feedback."""
        args = agent.build_execute_args(task_desc, "")
        run = agent._run_cli_streaming(
            args,
            on_line=on_line,
            no_output_timeout=no_output_timeout,
        )
        try:
            return await asyncio.wait_for(run, timeout=timeout)
        except WorkerNeedsFeedback as e:
            if _feedback_round >= 1:
                return f"[Worker asked for feedback again; giving up] {e.question}"
            render.render_worker_feedback_request(agent_name, e.question)
            prompt = (
                f"Worker '{agent_name}' requested feedback while doing their task:\n\n"
                f"**Their question:** {e.question}\n\n"
                "Reply with a short, direct guidance (one or two sentences). "
                "Your reply will be appended to their task and they will be re-run."
            )
            try:
                guidance = await asyncio.wait_for(
                    self.lead.send(prompt, continue_session=True),
                    timeout=lead_timeout,
                )
            except asyncio.TimeoutError:
                return f"[Lead did not respond in time to feedback request] {e.question}"
            guided_task = f"{task_desc}\n\n[Lead feedback]: {guidance.strip()}"
            return await self._run_worker_with_feedback(
                agent=agent,
                agent_name=agent_name,
                task_desc=guided_task,
                task=task,
                timeout=timeout,
                no_output_timeout=no_output_timeout,
                lead_timeout=lead_timeout,
                on_line=on_line,
                _feedback_round=_feedback_round + 1,
            )

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

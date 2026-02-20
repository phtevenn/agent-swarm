import pLimit from 'p-limit';
import { Task } from './task.js';
import { MessageBus } from './message-bus.js';
import { WorkerNeedsFeedback } from './agents/base.js';
import type { BaseAgent } from './agents/base.js';
import type { Config } from './config/schema.js';
import type { DelegateRequest, WorkerResult, OrchestratorCallbacks } from '../types.js';

const DELEGATE_RE = /<swarm:delegate>\s*([\s\S]*?)\s*<\/swarm:delegate>/;
const NEED_FEEDBACK_RE = /<swarm:need-feedback>\s*([\s\S]*?)\s*<\/swarm:need-feedback>/;

const FAILURE_PATTERNS: [RegExp, string][] = [
  [/429|rateLimitExceeded|Too Many Requests/i, 'rate_limit'],
  [/RESOURCE_EXHAUSTED|No capacity available|MODEL_CAPACITY_EXHAUSTED/i, 'capacity'],
  [/Timed out after \d+s/i, 'timeout'],
  [/produced no output for \d+s/i, 'no_output'],
  [/run_shell_command.*not found|Tool .* not found/i, 'tool_unavailable'],
];

function classifyFailure(err: string): string {
  for (const [re, kind] of FAILURE_PATTERNS) {
    if (re.test(err)) return kind;
  }
  return 'error';
}

function buildResultsSummary(results: WorkerResult[]): string {
  return results.map(r => {
    const status = r.status === 'failed' && r.failure_kind
      ? `**FAILED** (${r.failure_kind})`
      : r.status === 'failed' ? '**FAILED**' : 'OK';
    return `## Worker: ${r.agent}\n### Task: ${r.task}\n### Status: ${status}\n### Result:\n${r.result}`;
  }).join('\n\n');
}

function buildFollowup(results: WorkerResult[], roundIndex = 0): string {
  const summary = buildResultsSummary(results);
  const failed = results.filter(r => r.status === 'failed');
  let instruction: string;
  if (failed.length > 0) {
    instruction = (roundIndex > 0 ? '[Re-delegation round] ' : '') +
      'One or more tasks **failed** (e.g. rate limit or capacity). ' +
      'You may re-delegate the failed task(s) to a different worker by including ' +
      'a new <swarm:delegate> block with the same task assigned to another agent, ' +
      'or complete the task(s) yourself in your response.';
  } else {
    instruction = 'Please review the results and provide a summary to the user.';
  }
  return `The following delegated tasks have completed:\n\n${summary}\n\n${instruction}`;
}

function buildSystemPrompt(workers: Record<string, BaseAgent>): string {
  const enabled = Object.entries(workers).filter(([, a]) => a.enabled);
  if (!enabled.length) return '';

  const workerLines = enabled.map(([name]) => `  - ${name}`).join('\n');
  return `You are the lead agent in a coding agent swarm. You have worker agents available that you can delegate tasks to. You should work like a normal coding agent — answer questions, write code, make edits directly. Delegation is optional; use it when:
  - The task is large and can be parallelized
  - The user explicitly asks you to delegate
  - Different subtasks are independent and would benefit from parallel execution

Available workers:
${workerLines}

To delegate, include a block like this in your response:

<swarm:delegate>
[{"agent": "worker-name", "task": "description of what to do"}]
</swarm:delegate>

You can include multiple tasks in the array. Any text outside the delegate block is shown to the user normally. After delegation completes, you will receive the results and can respond to the user.

Workers can ask you for feedback mid-task by outputting:
<swarm:need-feedback>their question</swarm:need-feedback>
When that happens you will be asked to provide a short guidance reply; the worker will then be re-run with your feedback. Reply concisely.

When a worker fails (e.g. rate limit, capacity, or timeout), you will see their result marked as FAILED with a reason. You can then either:
  (1) Re-delegate the same task to a different worker by including a new <swarm:delegate> block that assigns the task to another agent (e.g. codex or cursor),
  (2) Or complete the task yourself in your response.
Prefer re-delegating to another worker when the failure is due to rate limits or capacity.

If delegation is unnecessary, just respond normally without any delegate block.`;
}

export class Orchestrator {
  private lead: BaseAgent;
  private workers: Record<string, BaseAgent>;
  private bus: MessageBus;
  private systemPrompt: string;
  readonly config: Config;

  constructor(config: Config, lead: BaseAgent, workers: BaseAgent[]) {
    this.config = config;
    this.lead = lead;
    this.workers = Object.fromEntries(workers.map(w => [w.name, w]));
    this.bus = new MessageBus(config.swarm.bus_dir);
    this.systemPrompt = buildSystemPrompt(this.workers);
  }

  get leadName(): string { return this.lead.name; }
  get workerNames(): string[] { return Object.keys(this.workers); }

  async chat(message: string, callbacks: OrchestratorCallbacks = {}): Promise<void> {
    const { lead_timeout: leadTimeout, max_parallel: maxParallel, worker_timeout: workerTimeout, no_output_timeout: noOutputTimeout } = this.config.swarm.tasks;

    let response = await withTimeout(
      this.lead.send(message, { systemPrompt: this.systemPrompt || undefined, continueSession: true }),
      leadTimeout,
    );

    for (let round = 0; round < 5; round++) {
      const match = DELEGATE_RE.exec(response);
      if (!match) break;

      const userText = response.replace(DELEGATE_RE, '').trim();
      if (userText) callbacks.onLeadChunk?.(userText);

      let tasks: DelegateRequest[];
      try {
        tasks = JSON.parse(match[1]) as DelegateRequest[];
      } catch {
        // Malformed delegation block — treat as plain text
        callbacks.onLeadDone?.(response);
        return;
      }

      callbacks.onDelegateStart?.(tasks);
      const results = await this.runDelegations(tasks, callbacks, { workerTimeout, noOutputTimeout, leadTimeout, maxParallel });
      callbacks.onDelegateEnd?.(results);

      const followup = buildFollowup(results, round);
      response = await withTimeout(
        this.lead.send(followup, { continueSession: true }),
        leadTimeout,
      );
    }

    callbacks.onLeadDone?.(response);
  }

  private async runDelegations(
    requests: DelegateRequest[],
    callbacks: OrchestratorCallbacks,
    opts: { workerTimeout: number; noOutputTimeout: number; leadTimeout: number; maxParallel: number },
  ): Promise<WorkerResult[]> {
    const limit = pLimit(opts.maxParallel);

    return Promise.all(requests.map(req => limit(async () => {
      const { agent: agentName, task: taskDesc } = req;
      const agent = this.workers[agentName];
      const taskObj = new Task({ title: taskDesc, assigned_to: agentName, created_by: this.lead.name });
      taskObj.assign(agentName);
      this.bus.publishTask(taskObj);

      if (!agent || !agent.enabled) {
        const error = `Worker '${agentName}' not available`;
        taskObj.fail(error);
        this.bus.publishTask(taskObj);
        const result: WorkerResult = { agent: agentName, task: taskDesc, result: error, status: 'failed', failure_kind: 'error' };
        callbacks.onWorkerFail?.(agentName, error, result);
        return result;
      }

      taskObj.start();
      this.bus.publishTask(taskObj);
      this.bus.updateStatus(agentName, { state: 'working', task_id: taskObj.id });

      const startedAt = Date.now();

      const onLine = (line: string) => {
        const m = NEED_FEEDBACK_RE.exec(line);
        if (m) return { stop: true as const, question: m[1].trim() };
        callbacks.onWorkerLine?.(agentName, line);
        return null;
      };

      try {
        const result = await this.runWorkerWithFeedback(agent, agentName, taskDesc, taskObj, opts, onLine);
        const elapsed = Math.round((Date.now() - startedAt) / 1000);
        taskObj.complete(result);
        this.bus.publishTask(taskObj);
        const wr: WorkerResult = { agent: agentName, task: taskDesc, result, status: 'ok', elapsed };
        callbacks.onWorkerDone?.(agentName, wr);
        return wr;
      } catch (err) {
        const errStr = err instanceof Error ? err.message : String(err);
        const elapsed = Math.round((Date.now() - startedAt) / 1000);
        taskObj.fail(errStr);
        this.bus.publishTask(taskObj);
        const kind = classifyFailure(errStr);
        const wr: WorkerResult = { agent: agentName, task: taskDesc, result: errStr, status: 'failed', failure_kind: kind, elapsed };
        callbacks.onWorkerFail?.(agentName, errStr, wr);
        return wr;
      } finally {
        this.bus.updateStatus(agentName, { state: 'idle' });
      }
    })));
  }

  private async runWorkerWithFeedback(
    agent: BaseAgent,
    agentName: string,
    taskDesc: string,
    _task: Task,
    opts: { workerTimeout: number; noOutputTimeout: number; leadTimeout: number },
    onLine: (line: string) => { stop: true; question: string } | null,
    feedbackRound = 0,
  ): Promise<string> {
    const args = agent.buildExecuteArgs(taskDesc, '');
    const run = agent.runCliStreaming(args, onLine, opts.noOutputTimeout);

    try {
      return await withTimeout(run, opts.workerTimeout);
    } catch (err) {
      if (err instanceof WorkerNeedsFeedback) {
        if (feedbackRound >= 1) return `[Worker asked for feedback again; giving up] ${err.question}`;
        const prompt = `Worker '${agentName}' requested feedback while doing their task:\n\n**Their question:** ${err.question}\n\nReply with a short, direct guidance (one or two sentences). Your reply will be appended to their task and they will be re-run.`;
        let guidance: string;
        try {
          guidance = await withTimeout(this.lead.send(prompt, { continueSession: true }), opts.leadTimeout);
        } catch {
          return `[Lead did not respond in time to feedback request] ${err.question}`;
        }
        const guidedTask = `${taskDesc}\n\n[Lead feedback]: ${guidance.trim()}`;
        return this.runWorkerWithFeedback(agent, agentName, guidedTask, _task, opts, onLine, feedbackRound + 1);
      }
      throw err;
    }
  }

  async getStatus(): Promise<Record<string, Record<string, unknown>>> {
    const statuses: Record<string, Record<string, unknown>> = {};
    for (const name of [this.lead.name, ...Object.keys(this.workers)]) {
      statuses[name] = this.bus.readStatus(name) ?? { state: 'idle' };
    }
    return statuses;
  }
}

function withTimeout<T>(promise: Promise<T>, seconds: number): Promise<T> {
  return Promise.race([
    promise,
    new Promise<T>((_, reject) =>
      setTimeout(() => reject(new Error(`Timed out after ${seconds}s`)), seconds * 1000)
    ),
  ]);
}

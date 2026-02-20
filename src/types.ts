/**
 * Shared TypeScript interfaces for Agent Swarm.
 * Used by both lib/ (orchestration) and UI (Ink components).
 */

export type AgentType = 'claude-code' | 'codex' | 'cursor' | 'gemini';
export type ApprovalMode = 'full-auto' | 'auto-edit' | 'suggest' | 'default';
export type TaskStatus =
  | 'pending'
  | 'assigned'
  | 'in_progress'
  | 'completed'
  | 'failed'
  | 'cancelled';

export type WorkerStatus = 'running' | 'done' | 'failed';

/** Live state of a worker during delegation — drives WorkerPanel UI. */
export interface WorkerState {
  name: string;
  task: string;
  status: WorkerStatus;
  lastLine?: string;
  startedAt: number;
  endedAt?: number;
  output?: string;
  error?: string;
}

/** A message in the chat history. */
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  text: string;
  timestamp: number;
}

/** A single delegation request from the lead. */
export interface DelegateRequest {
  agent: string;
  task: string;
}

/** Result returned by a worker after completing (or failing) a task. */
export interface WorkerResult {
  agent: string;
  task: string;
  result: string;
  status: 'ok' | 'failed';
  failure_kind?: string;
  elapsed?: number;
}

/** Callbacks the Orchestrator fires into the UI layer. */
export interface OrchestratorCallbacks {
  /** A chunk of the lead's streaming response. */
  onLeadChunk?: (chunk: string) => void;
  /** Lead finished responding (full text). */
  onLeadDone?: (full: string) => void;
  /** Delegation round started. */
  onDelegateStart?: (tasks: DelegateRequest[]) => void;
  /** Single stdout line from a worker. */
  onWorkerLine?: (name: string, line: string) => void;
  /** Worker completed successfully. */
  onWorkerDone?: (name: string, result: WorkerResult) => void;
  /** Worker failed. */
  onWorkerFail?: (name: string, error: string, result: WorkerResult) => void;
  /** All workers in this delegation round finished. */
  onDelegateEnd?: (results: WorkerResult[]) => void;
}

/** A single item in the immutable Static history (chat message or worker result). */
export type HistoryItem =
  | { type: 'message'; msg: ChatMessage }
  | { type: 'result'; worker: WorkerState };

/** Props passed from cli.tsx to app.tsx. */
export interface AppProps {
  prompt?: string;
  config?: string;
  trust?: boolean;
  verbose?: boolean;
  tmux?: boolean;
  iterm2?: boolean;
  // Pre-loaded by cli.tsx before render() so App never needs to handle trust failures
  cfg?: import('./lib/config/schema.js').Config;
  configSource?: string;
}

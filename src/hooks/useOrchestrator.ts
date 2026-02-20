import { useCallback, useRef } from 'react';
import type { OrchestratorCallbacks, DelegateRequest, WorkerResult } from '../types.js';

export interface OrchestratorHookCallbacks {
  onLeadChunk: (chunk: string) => void;
  onLeadDone: (full: string) => void;
  onDelegateStart: (tasks: DelegateRequest[]) => void;
  onWorkerLine: (name: string, line: string) => void;
  onWorkerDone: (name: string, result: WorkerResult) => void;
  onWorkerFail: (name: string, error: string, result: WorkerResult) => void;
  onDelegateEnd: (results: WorkerResult[]) => void;
}

// The actual Orchestrator class from lib/ — imported at runtime
// We use a type-only import to avoid circular dep issues during parallel dev
type OrchestratorClass = {
  chat: (message: string, callbacks: OrchestratorCallbacks) => Promise<void>;
};

export function useOrchestrator(callbacks: OrchestratorHookCallbacks) {
  const orchRef = useRef<OrchestratorClass | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const setOrchestrator = useCallback((orch: OrchestratorClass) => {
    orchRef.current = orch;
  }, []);

  const submit = useCallback(async (message: string) => {
    if (!orchRef.current) return;
    abortRef.current = new AbortController();

    await orchRef.current.chat(message, {
      onLeadChunk: callbacks.onLeadChunk,
      onLeadDone: callbacks.onLeadDone,
      onDelegateStart: callbacks.onDelegateStart,
      onWorkerLine: callbacks.onWorkerLine,
      onWorkerDone: callbacks.onWorkerDone,
      onWorkerFail: callbacks.onWorkerFail,
      onDelegateEnd: callbacks.onDelegateEnd,
    });
  }, [callbacks]);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const getOrchestrator = useCallback(() => orchRef.current, []);

  return { submit, cancel, setOrchestrator, getOrchestrator };
}

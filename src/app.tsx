import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Box, Text, Static, useInput, useApp } from 'ink';
import TextInput from 'ink-text-input';
import { Banner } from './components/Banner.js';
import { Message } from './components/Message.js';
import { WorkerPanel } from './components/WorkerPanel.js';
import { ResultPanel } from './components/ResultPanel.js';
import { useOrchestrator } from './hooks/useOrchestrator.js';
import type { AppProps, ChatMessage, WorkerState, DelegateRequest, WorkerResult } from './types.js';

let msgCounter = 0;
const mkId = () => `msg-${++msgCounter}`;

export default function App({ prompt, verbose, cfg: initialCfg, configSource: initialConfigSource }: AppProps) {
  const { exit } = useApp();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [workers, setWorkers] = useState<WorkerState[]>([]);
  const [delegating, setDelegating] = useState(false);
  const [streaming, setStreaming] = useState('');
  const [busy, setBusy] = useState(false);
  const [bannerInfo, setBannerInfo] = useState<{
    workspace: string; configSource: string; leadName: string;
    workerNames: string[]; approvalMode: string;
  } | null>(null);
  const [resultPanels, setResultPanels] = useState<WorkerState[]>([]);

  // Throttle high-frequency updates (streaming chunks + worker lines) to reduce
  // Ink re-render frequency and prevent terminal blinking.
  const streamingBufRef = useRef('');
  const workerLineBufRef = useRef<Record<string, string>>({});

  useEffect(() => {
    const streamId = setInterval(() => {
      const buf = streamingBufRef.current;
      if (buf) setStreaming(buf);
    }, 80);

    const workerLineId = setInterval(() => {
      const updates = workerLineBufRef.current;
      if (Object.keys(updates).length === 0) return;
      const snapshot = { ...updates };
      workerLineBufRef.current = {};
      setWorkers(ws => ws.map(w => w.name in snapshot ? { ...w, lastLine: snapshot[w.name] } : w));
    }, 100);

    return () => { clearInterval(streamId); clearInterval(workerLineId); };
  }, []);

  const onLeadChunk = useCallback((chunk: string) => {
    streamingBufRef.current += chunk;
  }, []);

  const onLeadDone = useCallback((full: string) => {
    streamingBufRef.current = '';
    setStreaming('');
    setMessages(m => [...m, { id: mkId(), role: 'assistant', text: full, timestamp: Date.now() }]);
    setBusy(false);
  }, []);

  const onDelegateStart = useCallback((tasks: DelegateRequest[]) => {
    setDelegating(true);
    setWorkers(tasks.map(t => ({
      name: t.agent,
      task: t.task,
      status: 'running' as const,
      startedAt: Date.now(),
    })));
  }, []);

  const onWorkerLine = useCallback((name: string, line: string) => {
    workerLineBufRef.current[name] = line;
  }, []);

  const onWorkerDone = useCallback((name: string, result: WorkerResult) => {
    setWorkers(ws => ws.map(w => w.name === name
      ? { ...w, status: 'done' as const, endedAt: Date.now(), output: result.result }
      : w
    ));
  }, []);

  const onWorkerFail = useCallback((name: string, error: string) => {
    setWorkers(ws => ws.map(w => w.name === name
      ? { ...w, status: 'failed' as const, endedAt: Date.now(), error }
      : w
    ));
  }, []);

  const onDelegateEnd = useCallback((_results: WorkerResult[]) => {
    setDelegating(false);
    // Push completed workers into result panels (permanent history)
    setWorkers(current => {
      setResultPanels(prev => [...prev, ...current]);
      return [];
    });
  }, []);

  const { submit, cancel, setOrchestrator, getOrchestrator } = useOrchestrator({
    onLeadChunk, onLeadDone, onDelegateStart, onWorkerLine, onWorkerDone, onWorkerFail, onDelegateEnd,
  });

  // Initialize orchestrator on mount.
  // Trust check and config loading already handled in cli.tsx before render().
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { createAgent } = await import('./lib/agents/index.js');
        const { Orchestrator } = await import('./lib/orchestrator.js');
        const { loadConfigWithFallback } = await import('./lib/config/loader.js');

        const [cfg, source] = initialCfg
          ? [initialCfg, initialConfigSource ?? 'config']
          : loadConfigWithFallback();
        const cwd = process.cwd();
        const mode = cfg.swarm.approval_mode;

        const lead = createAgent(cfg.swarm.lead, cwd, mode);
        const workerAgents = cfg.swarm.workers
          .filter(w => w.enabled)
          .map(w => createAgent(w, cwd, mode));
        const orch = new Orchestrator(cfg, lead, workerAgents);

        if (cancelled) return;
        setOrchestrator(orch);
        setBannerInfo({
          workspace: cwd,
          configSource: source,
          leadName: lead.name,
          workerNames: workerAgents.map(w => w.name),
          approvalMode: mode,
        });

        // One-shot mode
        if (prompt) {
          setBusy(true);
          setMessages(m => [...m, { id: mkId(), role: 'user', text: prompt, timestamp: Date.now() }]);
          await submit(prompt);
          setTimeout(() => exit(), 200);
        }
      } catch (err) {
        if (!cancelled) {
          setMessages(m => [...m, {
            id: mkId(), role: 'system', timestamp: Date.now(),
            text: `Error: ${err instanceof Error ? err.message : String(err)}`,
          }]);
        }
      }
    })();
    return () => { cancelled = true; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const addSystem = useCallback((text: string) => {
    setMessages(m => [...m, { id: mkId(), role: 'system', text, timestamp: Date.now() }]);
  }, []);

  const handleSlashCommand = useCallback(async (cmd: string): Promise<boolean> => {
    const [name, ...args] = cmd.slice(1).trim().toLowerCase().split(/\s+/);
    switch (name) {
      case 'help':
        addSystem(
          'Slash commands:\n' +
          '  /help      Show this help\n' +
          '  /workers   Show worker status\n' +
          '  /check     Health-check all agent CLIs\n' +
          '  /trust     Trust current workspace\n' +
          '  /exit      Exit swarm\n' +
          '  /quit\n' +
          '\n' +
          'Anything else is sent to the lead agent.'
        );
        return true;

      case 'exit':
      case 'quit':
      case 'q':
        exit();
        return true;

      case 'trust': {
        const { trustWorkspace } = await import('./lib/trust.js');
        trustWorkspace(process.cwd());
        addSystem(`Trusted workspace: ${process.cwd()}`);
        return true;
      }

      case 'workers': {
        const orch = getOrchestrator();
        if (!orch) { addSystem('Orchestrator not ready yet.'); return true; }
        const statuses = await (orch as unknown as { getStatus: () => Promise<Record<string, Record<string, unknown>>> }).getStatus();
        const lines = Object.entries(statuses).map(([name, s]) =>
          `  ${name.padEnd(16)} ${String((s as Record<string, unknown>)['state'] ?? 'idle')}`
        );
        addSystem('Agent status:\n' + lines.join('\n'));
        return true;
      }

      case 'check': {
        const { createAgent } = await import('./lib/agents/index.js');
        const { loadConfigWithFallback } = await import('./lib/config/loader.js');
        const [cfg] = loadConfigWithFallback();
        const mode = cfg.swarm.approval_mode;
        const agents = [
          createAgent(cfg.swarm.lead, process.cwd(), mode),
          ...cfg.swarm.workers.filter(w => w.enabled).map(w => createAgent(w, process.cwd(), mode)),
        ];
        addSystem('Running health checks…');
        const results = await Promise.all(agents.map(async a => {
          const ok = await a.healthCheck();
          return `  ${ok ? '✓' : '✗'} ${a.name}`;
        }));
        addSystem('Health checks:\n' + results.join('\n'));
        return true;
      }

      default:
        addSystem(`Unknown command: /${name}. Type /help for commands.`);
        return true;
    }
  }, [addSystem, exit, getOrchestrator]);

  const handleSubmit = useCallback(async (val: string) => {
    const trimmed = val.trim();
    if (!trimmed || busy) return;
    setInput('');

    if (trimmed.startsWith('/')) {
      await handleSlashCommand(trimmed);
      return;
    }

    setBusy(true);
    setMessages(m => [...m, { id: mkId(), role: 'user', text: trimmed, timestamp: Date.now() }]);
    await submit(trimmed);
  }, [busy, submit, handleSlashCommand]);

  useInput((input, key) => {
    if (key.ctrl && input === 'c') {
      cancel();
      exit();
    }
  });

  // All static items: banner + messages + result panels
  const staticItems: Array<{ type: 'banner' } | { type: 'message'; msg: ChatMessage } | { type: 'result'; worker: WorkerState }> = [];
  if (bannerInfo) staticItems.push({ type: 'banner' });
  for (const msg of messages) staticItems.push({ type: 'message', msg });
  for (const w of resultPanels) staticItems.push({ type: 'result', worker: w });

  return (
    <Box flexDirection="column">
      <Static items={staticItems}>
        {(item, i) => {
          if (item.type === 'banner' && bannerInfo) {
            return <Banner key="banner" {...bannerInfo} />;
          }
          if (item.type === 'message') {
            return <Message key={item.msg.id} {...item.msg} />;
          }
          if (item.type === 'result') {
            return <ResultPanel key={`result-${i}`} worker={item.worker} verbose={verbose} />;
          }
          return null;
        }}
      </Static>

      {delegating && <WorkerPanel workers={workers} />}

      {streaming && (() => {
        // Show only the last STREAM_WINDOW lines so the box has a fixed max-height.
        // Growing height forces Ink to repaint everything below it — the main
        // source of visible terminal blinking.
        const STREAM_WINDOW = 5;
        const lines = streaming.split('\n').slice(-STREAM_WINDOW);
        return (
          <Box paddingX={2} flexDirection="column">
            <Text dimColor>claude-code</Text>
            {lines.map((line, i) => (
              <Text key={i} color="cyan">{line}</Text>
            ))}
          </Box>
        );
      })()}

      {!prompt && (
        <Box borderStyle="single" borderColor={busy ? 'yellow' : 'green'} paddingX={1} marginTop={1}>
          <Text color={busy ? 'yellow' : 'green'}>{'> '}</Text>
          <TextInput
            value={input}
            onChange={setInput}
            onSubmit={handleSubmit}
            placeholder={busy ? 'Working...' : 'Talk to the lead agent...'}
          />
        </Box>
      )}
    </Box>
  );
}

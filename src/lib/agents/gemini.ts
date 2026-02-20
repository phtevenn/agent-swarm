import { BaseAgent, type StopSignal, WorkerNeedsFeedback } from './base.js';
import type { AgentConfig, ApprovalMode } from '../config/schema.js';

const APPROVAL_FLAGS: Record<ApprovalMode, string[]> = {
  'full-auto': ['--yolo'],
  'auto-edit': [],
  'suggest': ['--sandbox'],
  'default': [],
};

export class GeminiAgent extends BaseAgent {
  constructor(config: AgentConfig, workDir = '.', approvalMode: ApprovalMode = 'default') {
    super(config, workDir, approvalMode);
  }

  buildCmd(): string[] {
    const cmd = ['gemini', '--output-format', 'json'];
    cmd.push(...(APPROVAL_FLAGS[this.approvalMode] ?? []));
    if (this.config.model) cmd.push('-m', this.config.model);
    return cmd;
  }

  override buildExecuteArgs(task: string, context = ''): string[] {
    const prompt = context ? `${task}\n\n${context}` : task;
    return [...this.buildCmd(), '-p', prompt];
  }

  async healthCheck(): Promise<boolean> {
    try { await this.runCli(['gemini', '--version']); return true; }
    catch { return false; }
  }

  async send(message: string, opts?: { systemPrompt?: string }): Promise<string> {
    const prompt = opts?.systemPrompt ? `${opts.systemPrompt}\n\n${message}` : message;
    return this.execute(prompt);
  }

  async execute(task: string, context = ''): Promise<string> {
    const prompt = context ? `${task}\n\n${context}` : task;
    const raw = await this.runCli([...this.buildCmd(), '-p', prompt]);
    return this.extractResult(raw);
  }

  // Gemini buffers all output first (pretty-printed JSON), then shows response field
  override async runCliStreaming(
    args: string[],
    onLine?: (line: string) => StopSignal | null | undefined,
    noOutputTimeout?: number,
  ): Promise<string> {
    const allLines: string[] = [];
    await super.runCliStreaming(args, (line) => { allLines.push(line); return null; }, noOutputTimeout);

    const full = allLines.join('\n');
    const result = this.extractResult(full);

    if (onLine && result) {
      for (const part of result.split('\n')) {
        const sig = onLine(part);
        if (sig?.stop) throw new WorkerNeedsFeedback(sig.question, this.name);
      }
    }
    return result;
  }

  private extractResult(raw: string): string {
    // Gemini prefixes output with plain-text lines (e.g. "Loaded cached credentials.")
    // before the JSON blob. Find the first '{' and attempt to parse from there.
    const jsonStart = raw.indexOf('{');
    if (jsonStart !== -1) {
      try {
        const data = JSON.parse(raw.slice(jsonStart)) as Record<string, unknown>;
        if (typeof data === 'object' && data !== null) {
          const val = (data['response'] ?? data['result']) as string | undefined;
          if (val) return val;
        }
      } catch {}
    }

    // Fallback: try parsing the full string (no prefix-text case)
    try {
      const data = JSON.parse(raw) as Record<string, unknown>;
      if (typeof data === 'object' && data !== null) {
        const val = (data['response'] ?? data['result']) as string | undefined;
        if (val) return val;
      }
    } catch {}

    // Last resort: scan each complete single-line JSON object and take the last
    // one with a response/result field (handles streaming multiple JSON chunks).
    let lastResult: string | null = null;
    for (const line of raw.split('\n')) {
      const trimmed = line.trim();
      if (!trimmed.startsWith('{') || !trimmed.endsWith('}')) continue;
      try {
        const data = JSON.parse(trimmed) as Record<string, unknown>;
        const val = (data['response'] ?? data['result']) as string | undefined;
        if (val) lastResult = val;
      } catch {}
    }
    if (lastResult !== null) return lastResult;

    return raw;
  }
}

import { BaseAgent, type StopSignal } from './base.js';
import type { AgentConfig, ApprovalMode } from '../config/schema.js';

const APPROVAL_FLAGS: Record<ApprovalMode, string[]> = {
  'full-auto': ['--yolo', '--trust'],
  'auto-edit': ['--trust'],
  'suggest': ['--mode', 'plan', '--trust'],
  'default': [],
};

export class CursorAgent extends BaseAgent {
  constructor(config: AgentConfig, workDir = '.', approvalMode: ApprovalMode = 'default') {
    super(config, workDir, approvalMode);
  }

  buildCmd(): string[] {
    const cmd = ['agent', '--print', '--output-format', 'json'];
    cmd.push(...(APPROVAL_FLAGS[this.approvalMode] ?? []));
    if (this.config.model) cmd.push('--model', this.config.model);
    return cmd;
  }

  async healthCheck(): Promise<boolean> {
    try { await this.runCli(['agent', '--version']); return true; }
    catch { return false; }
  }

  async send(message: string, opts?: { systemPrompt?: string; continueSession?: boolean }): Promise<string> {
    const cmd = this.buildCmd();
    if (opts?.continueSession && this.sessionStarted) cmd.push('--continue');
    cmd.push(message);
    const raw = await this.runCli(cmd);
    this.sessionStarted = true;
    return this.extractResult(raw);
  }

  async execute(task: string, context = ''): Promise<string> {
    const prompt = context ? `${task}\n\n${context}` : task;
    const raw = await this.runCli([...this.buildCmd(), prompt]);
    return this.extractResult(raw);
  }

  // Override streaming: parse JSON lines, forward readable form only
  override async runCliStreaming(
    args: string[],
    onLine?: (line: string) => StopSignal | null | undefined,
    noOutputTimeout?: number,
  ): Promise<string> {
    const rawLines: string[] = [];
    const wrappedOnLine = onLine
      ? (line: string): StopSignal | null | undefined => {
          rawLines.push(line);
          const readable = this.lineToReadable(line);
          for (const part of readable.split('\n')) {
            const sig = onLine(part);
            if (sig?.stop) return sig;
          }
          return null;
        }
      : (line: string): null => { rawLines.push(line); return null; };

    await super.runCliStreaming(args, wrappedOnLine, noOutputTimeout);
    return this.extractResult(rawLines.join('\n'));
  }

  private lineToReadable(line: string): string {
    const s = line.trim();
    if (!s.startsWith('{')) return s;
    try {
      const data = JSON.parse(s) as Record<string, unknown>;
      return ((data['result'] ?? data['text'] ?? s) as string) || s;
    } catch { return s; }
  }

  private extractResult(raw: string): string {
    try {
      const data = JSON.parse(raw) as Record<string, unknown>;
      if (typeof data === 'object' && data !== null) {
        return (data['result'] ?? data['text'] ?? raw) as string;
      }
    } catch {}
    return raw;
  }
}

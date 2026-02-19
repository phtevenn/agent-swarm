import { BaseAgent } from './base.js';
import type { AgentConfig, ApprovalMode } from '../config/schema.js';

const APPROVAL_FLAGS: Record<ApprovalMode, string[]> = {
  'full-auto': ['--dangerously-skip-permissions'],
  'auto-edit': ['--permission-mode', 'acceptEdits'],
  'suggest': ['--permission-mode', 'plan'],
  'default': [],
};

export class ClaudeCodeAgent extends BaseAgent {
  constructor(config: AgentConfig, workDir = '.', approvalMode: ApprovalMode = 'default') {
    super(config, workDir, approvalMode);
  }

  buildCmd(): string[] {
    const cmd = ['claude', '--output-format', 'json'];
    cmd.push(...(APPROVAL_FLAGS[this.approvalMode] ?? []));
    if (this.config.model) cmd.push('--model', this.config.model);
    return cmd;
  }

  async healthCheck(): Promise<boolean> {
    try { await this.runCli(['claude', '--version']); return true; }
    catch { return false; }
  }

  async send(message: string, opts?: { systemPrompt?: string; continueSession?: boolean }): Promise<string> {
    const cmd = this.buildCmd();
    if (opts?.systemPrompt) cmd.push('--append-system-prompt', opts.systemPrompt);
    if (opts?.continueSession && this.sessionStarted) cmd.push('--continue');
    cmd.push('--print', message);
    const raw = await this.runCli(cmd);
    this.sessionStarted = true;
    return this.extractResult(raw);
  }

  async execute(task: string, context = ''): Promise<string> {
    const prompt = context ? `${task}\n\n${context}` : task;
    const raw = await this.runCli([...this.buildCmd(), '--print', prompt]);
    return this.extractResult(raw);
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

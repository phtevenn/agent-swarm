import { BaseAgent, type StopSignal } from './base.js';
import type { AgentConfig, ApprovalMode } from '../config/schema.js';

const APPROVAL_FLAGS: Record<ApprovalMode, string[]> = {
  'full-auto': ['--full-auto'],
  'auto-edit': ['-a', 'on-request', '-s', 'workspace-write'],
  'suggest': ['-a', 'untrusted', '-s', 'read-only'],
  'default': [],
};

export class CodexAgent extends BaseAgent {
  constructor(config: AgentConfig, workDir = '.', approvalMode: ApprovalMode = 'default') {
    super(config, workDir, approvalMode);
  }

  buildCmd(): string[] {
    const cmd = ['codex', 'exec', '--skip-git-repo-check'];
    cmd.push(...(APPROVAL_FLAGS[this.approvalMode] ?? []));
    if (this.config.model) cmd.push('--model', this.config.model);
    return cmd;
  }

  async healthCheck(): Promise<boolean> {
    try { await this.runCli(['codex', '--version']); return true; }
    catch { return false; }
  }

  async send(message: string): Promise<string> {
    return this.execute(message);
  }

  async execute(task: string, context = ''): Promise<string> {
    const prompt = context ? `${task}\n\n${context}` : task;
    const raw = await this.runCli([...this.buildCmd(), prompt]);
    return this.extractResult(raw);
  }

  override async runCliStreaming(
    args: string[],
    onLine?: (line: string) => StopSignal | null | undefined,
    noOutputTimeout?: number,
  ): Promise<string> {
    const raw = await super.runCliStreaming(args, onLine, noOutputTimeout);
    return this.extractResult(raw);
  }

  // Codex outputs a structured log ending with:
  //   tokens used\n<count>\n<clean final response>
  // Everything before that marker (headers, exec traces, warnings) is stripped.
  private extractResult(raw: string): string {
    const marker = '\ntokens used\n';
    const idx = raw.lastIndexOf(marker);
    if (idx !== -1) {
      const after = raw.slice(idx + marker.length);
      // First line is the numeric count ("2,282"), the rest is the clean response
      const response = after.split('\n').slice(1).join('\n').trim();
      if (response) return response;
    }
    return raw;
  }
}

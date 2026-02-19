import { BaseAgent } from './base.js';
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
    return this.runCli([...this.buildCmd(), prompt]);
  }
}

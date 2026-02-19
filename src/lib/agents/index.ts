import type { AgentConfig, ApprovalMode } from '../config/schema.js';
import type { BaseAgent } from './base.js';
import { ClaudeCodeAgent } from './claude-code.js';
import { CodexAgent } from './codex.js';
import { CursorAgent } from './cursor.js';
import { GeminiAgent } from './gemini.js';

export function createAgent(config: AgentConfig, workDir = '.', approvalMode: ApprovalMode = 'default'): BaseAgent {
  switch (config.agent) {
    case 'claude-code': return new ClaudeCodeAgent(config, workDir, approvalMode);
    case 'codex': return new CodexAgent(config, workDir, approvalMode);
    case 'cursor': return new CursorAgent(config, workDir, approvalMode);
    case 'gemini': return new GeminiAgent(config, workDir, approvalMode);
  }
}

export { BaseAgent, WorkerNeedsFeedback } from './base.js';
export { ClaudeCodeAgent } from './claude-code.js';
export { CodexAgent } from './codex.js';
export { CursorAgent } from './cursor.js';
export { GeminiAgent } from './gemini.js';

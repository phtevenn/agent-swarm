import { spawn } from 'child_process';
import * as readline from 'readline';
import type { AgentConfig, ApprovalMode } from '../config/schema.js';

export class WorkerNeedsFeedback extends Error {
  constructor(public question: string, public agentName = '') {
    super(question);
    this.name = 'WorkerNeedsFeedback';
  }
}

export interface StopSignal {
  stop: true;
  question: string;
}

export abstract class BaseAgent {
  protected config: AgentConfig;
  protected workDir: string;
  protected approvalMode: ApprovalMode;
  protected sessionStarted = false;
  readonly enabled: boolean;

  constructor(config: AgentConfig, workDir = '.', approvalMode: ApprovalMode = 'default') {
    this.config = config;
    this.workDir = workDir;
    this.approvalMode = approvalMode;
    this.enabled = config.enabled;
  }

  get name(): string { return this.config.agent; }

  abstract buildCmd(): string[];

  buildExecuteArgs(task: string, context = ''): string[] {
    const prompt = context ? `${task}\n\n${context}` : task;
    return [...this.buildCmd(), prompt];
  }

  abstract send(message: string, opts?: { systemPrompt?: string; continueSession?: boolean }): Promise<string>;
  abstract execute(task: string, context?: string): Promise<string>;

  async healthCheck(): Promise<boolean> { return true; }

  protected async runCli(args: string[], stdin?: string): Promise<string> {
    return new Promise((resolve, reject) => {
      const child = spawn(args[0], args.slice(1), {
        cwd: this.workDir,
        stdio: ['pipe', 'pipe', 'pipe'],
      });
      const chunks: Buffer[] = [];
      const errChunks: Buffer[] = [];
      if (stdin) child.stdin.end(stdin, 'utf8');
      else child.stdin.end();
      child.stdout.on('data', (d: Buffer) => chunks.push(d));
      child.stderr.on('data', (d: Buffer) => errChunks.push(d));
      child.on('close', code => {
        if (code !== 0) {
          const err = Buffer.concat(errChunks).toString('utf8').trim();
          reject(new Error(`${args[0]} exited with code ${code}: ${err}`));
        } else {
          resolve(Buffer.concat(chunks).toString('utf8').trim());
        }
      });
      child.on('error', reject);
    });
  }

  runCliStreaming(
    args: string[],
    onLine?: (line: string) => StopSignal | null | undefined,
    noOutputTimeout?: number,
  ): Promise<string> {
    return new Promise((resolve, reject) => {
      const child = spawn(args[0], args.slice(1), {
        cwd: this.workDir,
        stdio: ['ignore', 'pipe', 'pipe'],
      });

      const lines: string[] = [];
      const errChunks: Buffer[] = [];
      let timer: ReturnType<typeof setTimeout> | null = null;
      let settled = false;

      const settle = (fn: () => void) => {
        if (settled) return;
        settled = true;
        if (timer) clearTimeout(timer);
        fn();
      };

      const resetTimer = () => {
        if (!noOutputTimeout) return;
        if (timer) clearTimeout(timer);
        timer = setTimeout(() => {
          child.kill();
          settle(() => reject(new Error(`${args[0]} produced no output for ${noOutputTimeout}s (killed). The agent may be stuck or not writing to stdout.`)));
        }, noOutputTimeout * 1000);
      };

      const rl = readline.createInterface({ input: child.stdout!, terminal: false });

      if (noOutputTimeout) resetTimer();

      rl.on('line', line => {
        if (noOutputTimeout) resetTimer();
        lines.push(line);
        try {
          const signal = onLine?.(line);
          if (signal?.stop) {
            child.kill();
            settle(() => reject(new WorkerNeedsFeedback(signal.question, this.name)));
          }
        } catch (e) {
          child.kill();
          settle(() => reject(e));
        }
      });

      child.stderr.on('data', (d: Buffer) => errChunks.push(d));

      child.on('close', code => {
        rl.close();
        settle(() => {
          if (code !== 0) {
            const err = Buffer.concat(errChunks).toString('utf8').trim();
            reject(new Error(`${args[0]} exited with code ${code}: ${err}`));
          } else {
            resolve(lines.join('\n'));
          }
        });
      });

      child.on('error', e => settle(() => reject(e)));
    });
  }
}

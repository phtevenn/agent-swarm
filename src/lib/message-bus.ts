import { mkdirSync, writeFileSync, readFileSync, existsSync, readdirSync, unlinkSync } from 'fs';
import { join } from 'path';
import { Task, type TaskData } from './task.js';

export class MessageBus {
  private tasksDir: string;
  private statusDir: string;
  private messagesDir: string;

  constructor(busDir: string) {
    this.tasksDir = join(busDir, 'tasks');
    this.statusDir = join(busDir, 'status');
    this.messagesDir = join(busDir, 'messages');
    this._ensureDirs();
  }

  private _ensureDirs(): void {
    for (const d of [this.tasksDir, this.statusDir, this.messagesDir]) {
      mkdirSync(d, { recursive: true });
    }
  }

  publishTask(task: Task): string {
    const path = join(this.tasksDir, `${task.id}.json`);
    writeFileSync(path, JSON.stringify(task.toJSON(), null, 2));
    return path;
  }

  readTask(taskId: string): Task | null {
    const path = join(this.tasksDir, `${taskId}.json`);
    if (!existsSync(path)) return null;
    return Task.fromJSON(JSON.parse(readFileSync(path, 'utf8')) as TaskData);
  }

  listTasks(): Task[] {
    return readdirSync(this.tasksDir)
      .filter(f => f.endsWith('.json'))
      .sort()
      .map(f => {
        try {
          return Task.fromJSON(JSON.parse(readFileSync(join(this.tasksDir, f), 'utf8')) as TaskData);
        } catch { return null; }
      })
      .filter((t): t is Task => t !== null);
  }

  updateStatus(agentName: string, status: Record<string, unknown>): void {
    const path = join(this.statusDir, `${agentName}.json`);
    writeFileSync(path, JSON.stringify({ agent: agentName, timestamp: new Date().toISOString(), ...status }, null, 2));
  }

  readStatus(agentName: string): Record<string, unknown> | null {
    const path = join(this.statusDir, `${agentName}.json`);
    if (!existsSync(path)) return null;
    return JSON.parse(readFileSync(path, 'utf8')) as Record<string, unknown>;
  }

  postMessage(from: string, to: string, content: string): void {
    const ts = new Date().toISOString().replace(/[:.]/g, '_');
    const path = join(this.messagesDir, `${ts}_${from}_to_${to}.json`);
    writeFileSync(path, JSON.stringify({ from, to, content, timestamp: new Date().toISOString() }, null, 2));
  }

  cleanup(): void {
    for (const dir of [this.tasksDir, this.statusDir, this.messagesDir]) {
      if (existsSync(dir)) {
        readdirSync(dir).filter(f => f.endsWith('.json')).forEach(f => {
          try { unlinkSync(join(dir, f)); } catch {}
        });
      }
    }
  }
}

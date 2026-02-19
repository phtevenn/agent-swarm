import { randomBytes } from 'crypto';

export type TaskStatus = 'pending' | 'assigned' | 'in_progress' | 'completed' | 'failed' | 'cancelled';

export interface TaskData {
  id: string;
  parent_id?: string;
  title: string;
  description: string;
  status: TaskStatus;
  assigned_to?: string;
  created_by: string;
  result?: string;
  error?: string;
  created_at: string;
  updated_at: string;
}

export class Task {
  readonly id: string;
  parent_id?: string;
  title: string;
  description: string;
  status: TaskStatus;
  assigned_to?: string;
  created_by: string;
  result?: string;
  error?: string;
  created_at: string;
  updated_at: string;

  constructor(opts: { title: string; assigned_to?: string; created_by?: string; description?: string }) {
    this.id = randomBytes(6).toString('hex');
    this.title = opts.title;
    this.description = opts.description ?? '';
    this.status = 'pending';
    this.assigned_to = opts.assigned_to;
    this.created_by = opts.created_by ?? 'human';
    this.created_at = new Date().toISOString();
    this.updated_at = new Date().toISOString();
  }

  assign(agentName: string): void { this.assigned_to = agentName; this.status = 'assigned'; this._touch(); }
  start(): void { this.status = 'in_progress'; this._touch(); }
  complete(result: string): void { this.result = result; this.status = 'completed'; this._touch(); }
  fail(error: string): void { this.error = error; this.status = 'failed'; this._touch(); }
  cancel(): void { this.status = 'cancelled'; this._touch(); }

  toJSON(): TaskData {
    return {
      id: this.id, parent_id: this.parent_id, title: this.title,
      description: this.description, status: this.status,
      assigned_to: this.assigned_to, created_by: this.created_by,
      result: this.result, error: this.error,
      created_at: this.created_at, updated_at: this.updated_at,
    };
  }

  static fromJSON(data: TaskData): Task {
    const t = new Task({ title: data.title, assigned_to: data.assigned_to, created_by: data.created_by, description: data.description });
    Object.assign(t, data);
    return t;
  }

  private _touch(): void { this.updated_at = new Date().toISOString(); }
}

import { z } from 'zod';

export const AgentTypeSchema = z.enum(['claude-code', 'codex', 'cursor', 'gemini']);
export const ApprovalModeSchema = z.enum(['full-auto', 'auto-edit', 'suggest', 'default']);

export const AgentConfigSchema = z.object({
  agent: AgentTypeSchema,
  enabled: z.boolean().default(true),
  model: z.string().optional(),
  timeout: z.number().default(300),
  max_concurrent_tasks: z.number().default(2),
});

export const TaskSettingsSchema = z.object({
  worker_timeout: z.number().default(600),
  max_parallel: z.number().default(4),
  no_output_timeout: z.number().default(120),
  lead_timeout: z.number().default(600),
}).default({});

export const SwarmConfigSchema = z.object({
  bus_dir: z.string().default('.swarm'),
  approval_mode: ApprovalModeSchema.default('full-auto'),
  lead: AgentConfigSchema.default({ agent: 'claude-code' }),
  workers: z.array(AgentConfigSchema).default([
    { agent: 'codex', enabled: true, timeout: 300, max_concurrent_tasks: 2 },
    { agent: 'cursor', enabled: true, timeout: 300, max_concurrent_tasks: 2 },
  ]),
  tasks: TaskSettingsSchema,
});

export const ConfigSchema = z.object({
  swarm: SwarmConfigSchema,
});

export type AgentType = z.infer<typeof AgentTypeSchema>;
export type ApprovalMode = z.infer<typeof ApprovalModeSchema>;
export type AgentConfig = z.infer<typeof AgentConfigSchema>;
export type TaskSettings = z.infer<typeof TaskSettingsSchema>;
export type SwarmConfig = z.infer<typeof SwarmConfigSchema>;
export type Config = z.infer<typeof ConfigSchema>;

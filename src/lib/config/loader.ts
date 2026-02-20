import { readFileSync, existsSync } from 'fs';
import { join } from 'path';
import { homedir } from 'os';
import yaml from 'js-yaml';
import { ConfigSchema, type Config } from './schema.js';

const GLOBAL_CONFIG = join(homedir(), '.config', 'agent-swarm', 'swarm.yaml');

export function findConfig(cwd = process.cwd()): string | null {
  const candidates = [
    join(cwd, 'swarm.yaml'),
    join(cwd, 'config', 'swarm.yaml'),
    GLOBAL_CONFIG,
  ];
  return candidates.find(p => existsSync(p)) ?? null;
}

export function loadConfig(path: string): Config {
  const raw = yaml.load(readFileSync(path, 'utf8'));
  return ConfigSchema.parse(raw);
}

export function loadConfigWithFallback(explicit?: string): [Config, string] {
  if (explicit) return [loadConfig(explicit), explicit];
  const found = findConfig();
  if (found) return [loadConfig(found), found];
  return [ConfigSchema.parse({ swarm: {} }), 'built-in defaults'];
}

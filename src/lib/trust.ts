import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'fs';
import { join, resolve } from 'path';
import { homedir } from 'os';
import type { ApprovalMode } from './config/schema.js';

const TRUST_DIR = join(homedir(), '.config', 'agent-swarm');
const TRUST_FILE = join(TRUST_DIR, 'trusted.json');
const MODES_REQUIRING_TRUST = new Set<ApprovalMode>(['full-auto', 'auto-edit']);

interface TrustData { workspaces: string[]; }

function loadTrusted(): TrustData {
  if (!existsSync(TRUST_FILE)) return { workspaces: [] };
  try { return JSON.parse(readFileSync(TRUST_FILE, 'utf8')) as TrustData; }
  catch { return { workspaces: [] }; }
}

function saveTrusted(data: TrustData): void {
  mkdirSync(TRUST_DIR, { recursive: true });
  writeFileSync(TRUST_FILE, JSON.stringify(data, null, 2));
}

export function isWorkspaceTrusted(workspace: string): boolean {
  const resolved = resolve(workspace);
  return loadTrusted().workspaces.includes(resolved);
}

export function trustWorkspace(workspace: string): void {
  const resolved = resolve(workspace);
  const data = loadTrusted();
  if (!data.workspaces.includes(resolved)) {
    data.workspaces.push(resolved);
    saveTrusted(data);
  }
}

export function revokeTrust(workspace: string): boolean {
  const resolved = resolve(workspace);
  const data = loadTrusted();
  const idx = data.workspaces.indexOf(resolved);
  if (idx >= 0) { data.workspaces.splice(idx, 1); saveTrusted(data); return true; }
  return false;
}

export function requiresTrust(mode: ApprovalMode): boolean {
  return MODES_REQUIRING_TRUST.has(mode);
}

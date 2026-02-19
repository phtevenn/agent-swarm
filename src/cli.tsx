#!/usr/bin/env node
import React from 'react';
import { render } from 'ink';
import { Command } from 'commander';
import { loadConfigWithFallback } from './lib/config/loader.js';
import { requiresTrust, isWorkspaceTrusted, trustWorkspace } from './lib/trust.js';
import App from './app.js';
import type { AppProps } from './types.js';

const program = new Command();

program
  .name('swarm')
  .description('Agent Swarm -- orchestrate multiple coding agents')
  .option('-p, --prompt <text>', 'One-shot task (non-interactive)')
  .option('--config <path>', 'Config file path')
  .option('--trust', 'Trust workspace for this session')
  .option('-v, --verbose', 'Show full worker output')
  .action(() => {
    // Handled by render(<App />) below; this prevents commander from
    // defaulting to --help output when no subcommand is given.
  });

program
  .command('trust')
  .description('Trust or revoke trust for the current workspace')
  .option('--revoke', 'Revoke trust')
  .action(async (opts: { revoke?: boolean }) => {
    const { trustWorkspace, revokeTrust } = await import('./lib/trust.js');
    const cwd = process.cwd();
    if (opts.revoke) {
      const removed = revokeTrust(cwd);
      console.log(removed ? `Revoked trust for: ${cwd}` : `Workspace was not trusted: ${cwd}`);
    } else {
      trustWorkspace(cwd);
      console.log(`Trusted workspace: ${cwd}`);
    }
  });

program
  .command('status')
  .description('Show status of configured agents')
  .option('--config <path>', 'Config file path')
  .action(async (opts: { config?: string }) => {
    const { loadConfigWithFallback } = await import('./lib/config/loader.js');
    const { createAgent } = await import('./lib/agents/index.js');
    const { Orchestrator } = await import('./lib/orchestrator.js');
    const [cfg] = loadConfigWithFallback(opts.config);
    const cwd = process.cwd();
    const mode = cfg.swarm.approval_mode;
    const lead = createAgent(cfg.swarm.lead, cwd, mode);
    const workers = cfg.swarm.workers.filter(w => w.enabled).map(w => createAgent(w, cwd, mode));
    const orch = new Orchestrator(cfg, lead, workers);
    const statuses = await orch.getStatus();

    console.log(`\nAgent Status (approval: ${mode})\n`);
    console.log(`  ${'Agent'.padEnd(16)} ${'Role'.padEnd(8)} State`);
    console.log(`  ${'-'.repeat(40)}`);
    console.log(`  ${lead.name.padEnd(16)} ${'lead'.padEnd(8)} ${(statuses[lead.name] as Record<string, string>)?.state ?? 'idle'}`);
    for (const name of orch.workerNames) {
      console.log(`  ${name.padEnd(16)} ${'worker'.padEnd(8)} ${(statuses[name] as Record<string, string>)?.state ?? 'idle'}`);
    }
    console.log();
  });

program
  .command('check')
  .description('Run health checks on all configured agents')
  .option('--config <path>', 'Config file path')
  .action(async (opts: { config?: string }) => {
    const { loadConfigWithFallback } = await import('./lib/config/loader.js');
    const { createAgent } = await import('./lib/agents/index.js');
    const [cfg] = loadConfigWithFallback(opts.config);
    const cwd = process.cwd();
    const mode = cfg.swarm.approval_mode;
    const allAgents = [
      createAgent(cfg.swarm.lead, cwd, mode),
      ...cfg.swarm.workers.filter(w => w.enabled).map(w => createAgent(w, cwd, mode)),
    ];
    console.log('\nHealth checks:\n');
    for (const agent of allAgents) {
      const ok = await agent.healthCheck();
      console.log(`  ${ok ? '✓' : '✗'} ${agent.name}`);
    }
    console.log();
  });

program.parse();
const opts = program.opts<AppProps>();

// Only render Ink UI if no subcommand was invoked
if (!process.argv.slice(2).some(a => ['trust', 'status', 'check'].includes(a))) {
  const cwd = process.cwd();

  // Load config and check trust before launching Ink.
  // Doing this here gives a plain, visible error instead of a brief Ink flash.
  let cfg;
  let configSource: string;
  try {
    [cfg, configSource] = loadConfigWithFallback(opts.config);
  } catch (err) {
    console.error(`Error loading config: ${err instanceof Error ? err.message : err}`);
    process.exit(1);
  }

  const mode = cfg.swarm.approval_mode;

  if (opts.trust && requiresTrust(mode)) {
    trustWorkspace(cwd);
  }

  if (requiresTrust(mode) && !opts.trust && !isWorkspaceTrusted(cwd)) {
    console.error(
      `\nWorkspace not trusted: ${cwd}\n` +
      `Approval mode '${mode}' grants agents elevated permissions in this directory.\n\n` +
      `  swarm trust          Trust permanently\n` +
      `  swarm --trust        Trust for this session only\n`,
    );
    process.exit(1);
  }

  render(<App {...opts} cfg={cfg} configSource={configSource} />);
}

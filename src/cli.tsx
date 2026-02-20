#!/usr/bin/env node
import React, { useState } from 'react';
import { render } from 'ink';
import { Command } from 'commander';
import { loadConfigWithFallback } from './lib/config/loader.js';
import { requiresTrust, isWorkspaceTrusted, trustWorkspace } from './lib/trust.js';
import { TrustPrompt } from './components/TrustPrompt.js';
import App from './app.js';
import type { AppProps } from './types.js';
import type { Config } from './lib/config/schema.js';

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

  let cfg: Config;
  let configSource: string;
  try {
    [cfg, configSource] = loadConfigWithFallback(opts.config);
  } catch (err) {
    console.error(`Error loading config: ${err instanceof Error ? err.message : err}`);
    process.exit(1);
  }

  const mode = cfg.swarm.approval_mode;

  // --trust flag: persist trust and proceed immediately (no prompt)
  if (opts.trust && requiresTrust(mode)) {
    trustWorkspace(cwd);
  }

  const needsTrustPrompt = requiresTrust(mode) && !opts.trust && !isWorkspaceTrusted(cwd);

  // Root wrapper: shows TrustPrompt if needed, then the full App
  function Root() {
    const [trusted, setTrusted] = useState(!needsTrustPrompt);
    if (!trusted) {
      return <TrustPrompt workspace={cwd} mode={mode} onTrusted={() => setTrusted(true)} />;
    }
    return <App {...opts} cfg={cfg} configSource={configSource} />;
  }

  render(<Root />);
}

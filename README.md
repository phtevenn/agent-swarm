# Agent Swarm

Orchestration framework for coordinating multiple coding agents (Claude Code, Codex, Cursor, Gemini) with an interactive terminal UI.

> **Status:** Active development — TypeScript/Ink rewrite, core complete

## Overview

Agent Swarm launches a **lead agent** that accepts tasks from a human via an interactive TUI, optionally delegates subtasks to **worker agents** running in parallel, and synthesizes results back to you. Workers run their own CLI tools (`claude`, `codex`, `agent`, `gemini`) as subprocesses.

```
Human ──► Lead Agent (Claude Code by default)
              │
              ├──► Worker: codex   ──┐
              ├──► Worker: cursor  ──┤  file-based message bus (.swarm/)
              └──► Worker: gemini  ──┘
                                      │
              ◄── synthesized result ──┘
```

## Architecture

### Delegation protocol

The lead agent delegates by emitting a structured XML block in its response:

```xml
<swarm:delegate>
[{"agent": "codex", "task": "Add unit tests for utils/auth.ts"}]
</swarm:delegate>
```

The orchestrator detects this block, pauses the lead, dispatches the tasks to the named workers in parallel, waits for all results, then resumes the lead with the actual output. Workers can also request mid-task guidance from the lead:

```xml
<swarm:need-feedback>Should I use Jest or Vitest?</swarm:need-feedback>
```

The lead receives the question, replies with concise guidance, and the worker is re-run with the guidance appended to its task.

### Project structure

```
src/
├── cli.tsx               # Commander CLI entry point + Ink render
├── app.tsx               # Main Ink React UI
├── types.ts              # Shared TypeScript interfaces
├── hooks/
│   └── useOrchestrator.ts
├── components/
│   ├── Banner.tsx        # Config/mode header shown on startup
│   ├── Message.tsx       # Chat message renderer
│   ├── ResultPanel.tsx   # Worker result card (collapsed/verbose)
│   ├── TrustPrompt.tsx   # Trust confirmation dialog
│   ├── WorkerPanel.tsx   # Live worker status during delegation
│   └── WorkerRow.tsx     # Single worker row with spinner + last line
└── lib/
    ├── orchestrator.ts   # Delegate → parallel execute → synthesize
    ├── message-bus.ts    # File-based IPC via .swarm/
    ├── task.ts           # Task lifecycle model
    ├── trust.ts          # Workspace trust persistence
    ├── agents/
    │   ├── base.ts       # BaseAgent ABC with streaming subprocess helper
    │   ├── claude-code.ts
    │   ├── codex.ts
    │   ├── cursor.ts
    │   ├── gemini.ts
    │   └── index.ts      # createAgent factory
    └── config/
        ├── schema.ts     # Zod validation schemas
        └── loader.ts     # YAML → validated Config
config/
└── swarm.yaml            # Default configuration
```

### Supported agents

| Agent        | Role           | CLI binary | Notes                        |
|-------------|----------------|-----------|------------------------------|
| Claude Code | Lead / Worker  | `claude`  | Default lead                 |
| Codex       | Worker         | `codex`   | OpenAI Codex CLI             |
| Cursor      | Worker         | `agent`   | Cursor Agent CLI             |
| Gemini      | Lead / Worker  | `gemini`  | Google Gemini CLI            |

## Setup

```bash
# Install dependencies
pnpm install

# Build TypeScript
pnpm build

# Optional: link globally
npm link
```

Requires Node.js 18+ and `pnpm`. Each agent type also needs its own CLI installed and authenticated (`claude`, `codex`, `agent`, `gemini`).

## Usage

### Interactive mode (default)

```bash
# Launch interactive TUI
swarm

# Use a custom config file
swarm --config path/to/swarm.yaml

# Trust workspace and launch (skips trust prompt)
swarm --trust

# Show full worker output
swarm -v
```

### One-shot mode

```bash
# Submit a single task and exit
swarm --prompt "Refactor the auth module"
swarm -p "Add unit tests for utils/"
```

### Utility commands

```bash
# Show status of configured agents
swarm status

# Health-check all configured agent CLIs
swarm check

# Trust current workspace permanently
swarm trust

# Revoke trust
swarm trust --revoke
```

### In-TUI slash commands

| Command    | Description                        |
|-----------|------------------------------------|
| `/help`   | List available slash commands      |
| `/workers`| Show live agent status             |
| `/check`  | Run health checks on all agents    |
| `/trust`  | Trust current workspace            |
| `/exit`   | Exit (also `Ctrl+C`, `/quit`, `/q`)|

## Configuration

`config/swarm.yaml` is loaded by default. Override with `--config`.

```yaml
swarm:
  # Directory for inter-agent message bus files
  bus_dir: .swarm

  # Approval mode — inherited by ALL agents (lead + workers)
  # full-auto  — agents execute everything without human approval (requires trust)
  # auto-edit  — auto-approve file edits, prompt for shell commands (requires trust)
  # suggest    — read-only / plan mode; agents propose but don't execute
  # default    — each agent's built-in default behavior
  approval_mode: full-auto

  lead:
    agent: claude-code      # claude-code | codex | cursor | gemini
    # model: claude-sonnet-4-20250514
    # timeout: 300

  workers:
    - agent: codex
      # enabled: true
      # max_concurrent_tasks: 2
    - agent: cursor
      # enabled: true
    # - agent: gemini
    #   enabled: true

  tasks:
    worker_timeout: 600      # Max seconds per subtask
    max_parallel: 4          # Max concurrent subtasks
    no_output_timeout: 120   # Kill worker if silent for this long (seconds)
    lead_timeout: 600        # Max seconds to wait for the lead agent
```

### Workspace trust

Modes `full-auto` and `auto-edit` allow agents to execute code without human confirmation. Before using these modes, the tool will prompt you to explicitly trust the workspace. Trust is stored in `~/.config/agent-swarm/trusted.json`.

## How it works

1. You type a message in the TUI; the orchestrator forwards it to the lead agent.
2. The lead responds — either directly (no delegation needed) or with a `<swarm:delegate>` block naming worker agents and their tasks.
3. The orchestrator dispatches delegated tasks in parallel (up to `max_parallel` at once) and streams each worker's stdout live in the TUI.
4. If a worker emits a `<swarm:need-feedback>` block, the orchestrator pauses that worker, asks the lead for guidance, and re-runs the worker with the guidance appended.
5. When all workers finish, results (with failure classification for rate limits, timeouts, etc.) are fed back to the lead.
6. The lead synthesizes and responds to you.
7. This loop repeats up to 5 delegation rounds per user message to handle re-delegation on failures.

## Roadmap

### Done
- [x] TypeScript/Ink rewrite with interactive TUI
- [x] Streaming lead + live worker output with throttled re-renders
- [x] Parallel worker delegation with configurable concurrency
- [x] Worker feedback loop (`<swarm:need-feedback>`)
- [x] Failure classification and re-delegation (rate limit, timeout, capacity)
- [x] Workspace trust system
- [x] File-based message bus (`.swarm/`)
- [x] `status`, `check`, `trust` subcommands
- [x] One-shot (`--prompt`) mode

### Planned
- [ ] Discord bot for real-time status notifications
- [ ] Tmux multi-pane layout (one pane per agent)
- [ ] iTerm2 multi-tab layout
- [ ] Task dependency graphs (ordered subtasks)
- [ ] Agent output log files

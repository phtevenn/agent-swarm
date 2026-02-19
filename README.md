# Agent Swarm

Orchestration framework for coordinating multiple coding agents (Claude Code, Codex, Cursor Agent).

> **Status:** Early development — Phase 1

## Overview

Agent Swarm lets you configure a **lead agent** that accepts tasks from a human, breaks them down, and delegates subtasks to **worker agents** running in parallel. Results flow back through a shared message bus so the lead can synthesize a final outcome.

## Architecture

```
Human ──► Lead Agent (configurable)
              │
              ├──► Worker Agent A  ──┐
              ├──► Worker Agent B  ──┤  message bus (.swarm/)
              └──► Worker Agent C  ──┘
                                      │
              ◄── synthesized result ──┘
```

### Supported Agents

| Agent        | Role Support     | Spawn Method        |
|-------------|-----------------|---------------------|
| Claude Code | Lead / Worker   | `claude` CLI        |
| Codex       | Worker          | `codex` CLI         |
| Cursor Agent| Worker          | Cursor terminal     |

### Communication

Agents communicate through a file-based message bus under `.swarm/`:

- **tasks/** — task assignments from lead to workers
- **status/** — worker status updates
- **messages/** — inter-agent messages

## Setup

```bash
uv sync
uv sync --extra dev     # include dev tools
uv sync --extra all     # include all optional deps
```

## Usage

```bash
# Run with default config
swarm run "Refactor the auth module"

# Use a specific config
swarm --config config/swarm.yaml run "Add unit tests for utils/"

# Check agent status
swarm status
```

## Configuration

See `config/swarm.yaml` for the full configuration schema.

```yaml
swarm:
  lead:
    agent: claude-code
  workers:
    - agent: codex
    - agent: cursor
```

## Roadmap

### Phase 1 — Core Framework
- [x] Project scaffolding
- [ ] Configuration schema and loader
- [ ] Core orchestrator and task model
- [ ] Agent adapters (Claude Code, Codex, Cursor)
- [ ] File-based message bus
- [ ] CLI entry point

### Phase 2 — Extended Features
- [ ] Discord bot for status updates
- [ ] iTerm2 multi-window agent view
- [ ] Tmux layout support
- [ ] Direct human-to-worker messaging

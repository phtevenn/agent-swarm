# Agent Swarm

Orchestration framework for coordinating multiple coding agents (Claude Code, Codex, Cursor Agent, Gemini).

> **Status:** Early development — Phase 1 core complete, Phase 2 scaffolded

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

### Project Structure

```
src/swarm/
├── cli.py                  # Click CLI: run, status, check
├── config/
│   ├── schema.py           # Pydantic models for swarm.yaml
│   └── loader.py           # YAML → validated Config
├── core/
│   ├── task.py             # Task model with lifecycle methods
│   ├── message_bus.py      # File-based IPC via .swarm/
│   └── orchestrator.py     # Decompose → execute → synthesize pipeline
├── agents/
│   ├── base.py             # BaseAgent ABC with async subprocess helper
│   ├── claude_code.py      # `claude` CLI adapter (JSON output mode)
│   ├── codex.py            # `codex` CLI adapter
│   ├── cursor.py           # Cursor Agent (`agent` CLI)
│   └── gemini.py           # Google Gemini CLI (`gemini`)
├── discord/
│   └── bot.py              # Discord status notifications (Phase 2)
└── terminal/
    ├── tmux.py             # Tmux multi-pane layout (Phase 2)
    └── iterm2.py           # iTerm2 Python API layout (Phase 2)
```

### Supported Agents

| Agent        | Role Support   | Spawn Method    | Status       |
|-------------|----------------|-----------------|-------------|
| Claude Code | Lead / Worker | `claude` CLI   | Implemented |
| Codex       | Worker        | `codex` CLI    | Implemented |
| Cursor      | Worker        | `agent` CLI    | Implemented |
| Gemini      | Lead / Worker | `gemini` CLI   | Implemented |

### Communication

Agents communicate through a file-based message bus under `.swarm/`:

- **tasks/** — JSON task assignments from lead to workers
- **status/** — agent status updates (idle, working, etc.)
- **messages/** — inter-agent messages with timestamps

The bus supports async watching via `watchfiles` for real-time event processing.

## Setup

```bash
# Install dependencies
uv sync

# Include dev tools (pytest, ruff)
uv sync --extra dev

# Include all optional deps (discord.py, iterm2)
uv sync --extra all
```

## Usage

```bash
# Submit a task to the swarm
swarm run "Refactor the auth module"

# Use a specific config file
swarm --config config/swarm.yaml run "Add unit tests for utils/"

# Show agent status table
swarm status

# Health-check all configured agents
swarm check

# Enable debug logging
swarm -v run "Fix the login bug"
```

## Configuration

Edit `config/swarm.yaml` to change which agent leads, which agents are workers, and how tasks are managed.

```yaml
swarm:
  lead:
    agent: claude-code       # claude-code | codex | cursor | gemini
    # model: claude-sonnet-4-20250514
    # timeout: 300
  workers:
    - agent: codex
      # max_concurrent_tasks: 2
    - agent: cursor
      # enabled: false
    # - agent: gemini
    #   enabled: true
  tasks:
    worker_timeout: 600      # seconds per subtask
    max_parallel: 4          # concurrent subtasks

# Phase 2
# discord:
#   enabled: true
#   token_env: DISCORD_BOT_TOKEN
#   channel_id: 123456789
# terminal:
#   backend: tmux            # tmux | iterm2
#   layout: tiled            # tiled | horizontal | vertical
```

## Roadmap

### Phase 1 — Core Framework
- [x] Project scaffolding (uv, pyproject.toml)
- [x] Configuration schema and YAML loader (Pydantic)
- [x] Task model with lifecycle management
- [x] File-based message bus with async watchers
- [x] Core orchestrator (decompose → parallel execute → synthesize)
- [x] Agent adapters (Claude Code, Codex, Cursor)
- [x] CLI entry point (run, status, check)

### Phase 2 — Extended Features
- [ ] Discord bot for real-time status updates
- [ ] iTerm2 multi-tab agent view
- [ ] Tmux multi-pane layout support
- [ ] Direct human-to-worker messaging
- [ ] Agent output streaming / live tailing
- [ ] Task dependency graphs (subtask ordering)

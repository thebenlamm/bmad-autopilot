# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

BMAD Autopilot is a bash-based orchestration tool that automates the BMAD (Business-driven, Methodical, Agile Development) workflow. It manages the full story lifecycle: creation → development → code review.

## Scripts

| Script | Purpose |
|--------|---------|
| `bmad-autopilot.sh` | Full pipeline orchestration |
| `bmad-phase.sh` | Run single phases manually |
| `bmad-setup.sh` | Install/verify dependencies |

## Running the Tool

```bash
# Setup (first time)
./bmad-setup.sh

# Full pipeline
./bmad-autopilot.sh --project ~/myproject
./bmad-autopilot.sh --epic 0 --tmux
./bmad-autopilot.sh --yolo  # unattended mode

# Single phases
./bmad-phase.sh status
./bmad-phase.sh next
./bmad-phase.sh create 0-1-homepage
./bmad-phase.sh develop 0-1-homepage
./bmad-phase.sh review 0-1-homepage
```

## Dependencies

Required:
- `yq` - YAML parsing (`brew install yq`)
- `llm` CLI with plugins (`pip install llm && llm install llm-anthropic llm-gemini`)
- `gtimeout` or `timeout` (`brew install coreutils` on macOS)

Optional:
- `aider` - For automated development phase
- `claude` - Alternative to aider for development
- `tmux` - For dashboard mode

## Architecture

### Three-Phase Pipeline

1. **Story Creation** (Claude via `llm` CLI)
   - Reads `sprint-status.yaml` for stories with status `backlog`
   - Generates story markdown from epics and project context
   - Updates status to `ready-for-dev`

2. **Development** (aider or claude)
   - Picks up stories with status `ready-for-dev` or `in-progress`
   - Hands off to agentic coding tool
   - Updates status to `review`

3. **Code Review** (Claude Opus via `llm` CLI)
   - Runs adversarial review against git diff
   - CRITICAL issues → back to `in-progress`
   - No critical issues → `done`

### Expected Project Structure

The tool expects target projects to have:
```
docs/
  epics.md                      # Epic definitions (required)
  sprint-artifacts/
    sprint-status.yaml          # Story status tracking (required)
    *.md                        # Generated story files
    reviews/                    # Code review outputs
```

Alternative flat structure also supported:
```
epics.md
sprint-status.yaml
```

### Story Key Format

Stories use the format `{epic}-{story}-{slug}`, e.g., `0-1-homepage`. This is validated via regex to prevent command injection.

### Status State Machine

```
backlog → ready-for-dev → in-progress ↔ review → done
                              ↑______________|
                         (critical issues)
```

Also: `blocked` (after 3 consecutive API failures)

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `CLAUDE_MODEL` | `claude-sonnet-4-5-20250514` | Story creation |
| `AIDER_MODEL` | `claude-sonnet-4-5-20250514` | Development phase |
| `REVIEW_MODEL` | `claude-opus-4-20250514` | Code review |
| `LLM_TIMEOUT` | `300` | Seconds before LLM call timeout |

## Key Implementation Details

- Uses `mktemp` for all LLM context files to avoid shell escaping issues
- Log rotation keeps only last 10 log files in `logs/bmad-autopilot/`
- Tmux layout: main output (top), sprint status watch (bottom-left), log tail (bottom-right)
- `--yolo` mode passes `--yes-always` to aider for fully unattended operation

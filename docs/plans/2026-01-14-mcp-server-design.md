# BMAD MCP Server Design

**Date:** 2026-01-14
**Status:** Approved via llm-conclave consensus

## Overview

MCP server that exposes BMAD Autopilot functionality as tools callable by Claude Code. Enables orchestrating story creation, development, and code review across any BMAD project using multiple LLMs.

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Language | Python | Clean MCP SDK, easy subprocess handling |
| LLM calls | Shell to `llm` CLI | Multi-provider support, pre-configured API keys |
| Granularity | Coarse + fine-grained | `run_epic` for automation, individual tools for control |
| Development phase | Return instructions | Claude Code implements directly with full context |
| State | Stateless | Read `sprint-status.yaml` each call |
| Project context | `set_project` tool | Explicit, validated, with per-call override |

## Tools

| Tool | Purpose |
|------|---------|
| `bmad_set_project` | Set active project path |
| `bmad_status` | Get sprint status with counts |
| `bmad_next` | Get next actionable stories |
| `bmad_create_story` | Generate story from epics |
| `bmad_develop_story` | Get implementation instructions |
| `bmad_review_story` | Run adversarial code review |
| `bmad_update_status` | Update story status |
| `bmad_run_epic` | Orchestrate full epic |

## Architecture

```
bmad-autopilot/
├── bmad_mcp/
│   ├── __init__.py
│   ├── server.py        # MCP server, tool definitions
│   ├── project.py       # Project validation, path handling
│   ├── sprint.py        # Sprint status YAML operations
│   ├── llm.py           # LLM CLI wrapper with timeout
│   └── phases/
│       ├── __init__.py
│       ├── create.py    # Story creation
│       ├── develop.py   # Implementation instructions
│       └── review.py    # Code review
├── pyproject.toml
└── (existing bash scripts)
```

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `CLAUDE_MODEL` | `claude-sonnet-4-5-20250514` | Story creation |
| `REVIEW_MODEL` | `claude-opus-4-20250514` | Code review |
| `LLM_TIMEOUT` | `300` | Seconds per LLM call |

## Response Format

All tools return:
```python
{
    "success": bool,
    "data": {...},  # Tool-specific payload
    "error": str | None
}
```

## Dependencies

- `mcp>=1.0.0` - MCP Python SDK
- `pyyaml>=6.0` - YAML parsing

External (must be installed):
- `llm` CLI with `llm-anthropic`, `llm-gemini` plugins
- `yq` for bash script compatibility

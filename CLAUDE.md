# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

BMAD Autopilot orchestrates BMAD (Business-driven, Methodical, Agile Development) workflows. It manages the full story lifecycle: creation → development → code review using multiple LLMs.

**Two interfaces:**
1. **MCP Server** - Claude Code calls tools directly (recommended)
2. **CLI Scripts** - Bash scripts for manual/automated use

## MCP Server Usage Guide

The `bmad_mcp` package exposes BMAD tools via MCP protocol. **This is the recommended way to use BMAD Autopilot from Claude Code.**

### Quick Start

```
1. bmad_set_project({project_path: "~/Workspace/myproject"})  # REQUIRED FIRST
2. bmad_status()                                               # See current state
3. bmad_run_epic({epic_number: 0})                            # Get orchestration plan
4. Follow the plan: create → develop → review each story
```

### Response Format

**All tools return a `next_step` field** telling you exactly what to do next:

```json
{
  "success": true,
  "data": { ... },
  "next_step": {
    "action": "bmad_run_epic or bmad_status",
    "description": "Get epic plan or check sprint status"
  }
}
```

**Always follow the `next_step` guidance** - it ensures you don't skip workflow steps.

### Tool Reference

#### `bmad_set_project` (REQUIRED FIRST)
**Must be called before any other tool.**

```json
// Input
{"project_path": "/Users/ben/Workspace/myproject"}

// Output
{
  "success": true,
  "data": {
    "project_root": "/Users/ben/Workspace/myproject",
    "sprint_status": "/Users/ben/Workspace/myproject/docs/sprint-artifacts/sprint-status.yaml",
    "epics_file": "/Users/ben/Workspace/myproject/docs/epics.md",
    "status_summary": {"backlog": 5, "ready-for-dev": 2, "done": 3}
  },
  "next_step": {
    "action": "bmad_run_epic or bmad_status",
    "description": "Get epic plan or check sprint status"
  }
}
```

#### `bmad_status`
Get current sprint status with all stories and counts.

```json
// Output
{
  "success": true,
  "data": {
    "stories": {
      "0-1-homepage": "done",
      "0-2-navigation": "ready-for-dev",
      "1-1-auth-login": "backlog"
    },
    "summary": {"done": 1, "ready-for-dev": 1, "backlog": 1}
  }
}
```

#### `bmad_next`
Get next actionable stories with recommendations.

```json
// Output
{
  "success": true,
  "data": {
    "next_actions": {
      "ready-for-dev": ["0-2-navigation"],
      "backlog": ["1-1-auth-login", "1-2-auth-logout"]
    },
    "recommendations": [
      "Start development: 0-2-navigation - run bmad_develop_story",
      "Create story: 1-1-auth-login - run bmad_create_story"
    ]
  }
}
```

#### `bmad_create_story`
Generate a story file from epics using Claude. Updates status to `ready-for-dev`.

```json
// Input
{"story_key": "1-1-auth-login"}

// Output (story content is full markdown)
{
  "success": true,
  "data": {
    "story_key": "1-1-auth-login",
    "story_file": "/path/to/docs/sprint-artifacts/1-1-auth-login.md",
    "content": "# 1-1: User Authentication Login\n\n## User Story\nAs a user...",
    "status": "ready-for-dev"
  }
}
```

#### `bmad_develop_story`
**KEY TOOL**: Returns story content with implementation instructions for YOU (Claude) to execute directly. Updates status to `in-progress`.

```json
// Input
{"story_key": "0-2-navigation"}

// Output
{
  "success": true,
  "data": {
    "story_key": "0-2-navigation",
    "story_file": "/path/to/0-2-navigation.md",
    "story_content": "# 0-2: Navigation Component\n\n## Tasks\n- [ ] Create Nav component...",
    "tasks": [
      {"description": "Create Nav component", "completed": false, "is_subtask": false},
      {"description": "Add responsive menu", "completed": false, "is_subtask": true}
    ],
    "instructions": "## Implementation Instructions\n1. Read the story content...",
    "status": "in-progress"
  }
}
```

**After calling this tool, YOU should:**
1. Read the `story_content` and `tasks`
2. Implement each task in the target project
3. Check off tasks in the story file as you complete them
4. Run tests to verify acceptance criteria
5. Call `bmad_verify_implementation` to check readiness
6. If verification passes, call `bmad_review_story`

#### `bmad_verify_implementation` (NEW - Call Before Review)
**Verifies implementation is ready for review.** Checks git changes, task completion, and tests.

```json
// Input
{"story_key": "0-2-navigation"}

// Output (ready for review)
{
  "success": true,
  "data": {
    "story_key": "0-2-navigation",
    "ready_for_review": true,
    "has_changes": true,
    "files_changed": 5,
    "tasks_completed": 4,
    "tasks_total": 4,
    "tests_passed": true,
    "checks": {
      "git_changes": {"passed": true, "message": "5 files changed"},
      "task_completion": {"passed": true, "message": "4/4 tasks completed"},
      "tests": {"passed": true, "message": "All tests passed"}
    }
  },
  "next_step": {
    "action": "bmad_review_story",
    "args": {"story_key": "0-2-navigation"},
    "description": "Run code review"
  }
}

// Output (NOT ready)
{
  "success": true,
  "data": {
    "ready_for_review": false,
    "checks": {
      "git_changes": {"passed": true, "message": "3 files changed"},
      "task_completion": {"passed": false, "message": "2/4 tasks completed - finish tasks before review"},
      "tests": {"passed": false, "message": "Tests failed - fix before review"}
    }
  },
  "next_step": {
    "action": "continue implementation",
    "description": "Complete remaining tasks and fix failing tests"
  }
}
```

**This tool prevents premature reviews** by checking:
- Git has uncommitted or committed changes
- All tasks in the story file are checked off
- Tests pass (if npm test or pytest is available)

#### `bmad_review_story`
Run adversarial code review using Claude Opus. Compares git diff against story requirements.

```json
// Input
{"story_key": "0-2-navigation"}

// Output (no critical issues)
{
  "success": true,
  "data": {
    "story_key": "0-2-navigation",
    "review": "## Code Review: 0-2-navigation\n\n### Issues Found\n\n1. **MEDIUM**: Missing null check...",
    "has_critical_issues": false,
    "recommendation": "done",
    "review_file": "/path/to/reviews/0-2-navigation-review.md",
    "new_status": "done",
    "structured_issues": [
      {
        "severity": "MEDIUM",
        "file": "src/components/Nav.tsx",
        "line": "42",
        "issue": "Missing null check for user prop",
        "fix": "Add optional chaining: user?.name instead of user.name"
      }
    ]
  },
  "next_step": {
    "action": "bmad_next or bmad_run_epic",
    "description": "Story complete! Get next story to work on"
  }
}

// Output (has critical issues)
{
  "success": true,
  "data": {
    "story_key": "0-2-navigation",
    "review": "...",
    "has_critical_issues": true,
    "recommendation": "in-progress",
    "new_status": "in-progress",
    "structured_issues": [
      {
        "severity": "CRITICAL",
        "file": "src/api/auth.ts",
        "line": "15",
        "issue": "SQL injection vulnerability",
        "fix": "Use parameterized query: db.query('SELECT * FROM users WHERE id = ?', [userId])"
      }
    ]
  },
  "next_step": {
    "action": "fix issues then bmad_verify_implementation",
    "description": "Fix CRITICAL issues listed in structured_issues, then verify again"
  }
}
```

**The `structured_issues` array** provides structured, machine-readable issues:
- `severity`: CRITICAL, HIGH, MEDIUM, or LOW
- `file`: File path where the issue is located
- `line`: Line number (if identified)
- `issue`: Description of the problem
- `fix`: Specific fix recommendation

**If `has_critical_issues` is true:** Status is set to `in-progress`. Fix the issues in `structured_issues`, then call `bmad_verify_implementation` and re-review.

#### `bmad_update_status`
Manually update a story's status.

```json
// Input
{"story_key": "0-2-navigation", "status": "review"}

// Valid statuses: backlog, ready-for-dev, in-progress, review, done, blocked
```

#### `bmad_run_epic`
Get orchestration plan for a full epic. Shows all stories and recommended actions.

```json
// Input
{"epic_number": 0}

// Output
{
  "success": true,
  "data": {
    "epic_number": 0,
    "stories": {"0-1-homepage": "done", "0-2-navigation": "in-progress"},
    "by_status": {"done": ["0-1-homepage"], "in-progress": ["0-2-navigation"]},
    "plan": [
      {"action": "continue", "story_key": "0-2-navigation", "tool": "bmad_develop_story"}
    ],
    "progress": "1/2 stories done",
    "is_complete": false
  }
}
```

### Complete Workflow Example

**User:** "Run epic 0 for ~/Workspace/myproject"

**Claude should:**
```
1. bmad_set_project({project_path: "~/Workspace/myproject"})
   → Follow next_step guidance

2. bmad_run_epic({epic_number: 0})
   → Returns plan with stories to create/develop/review

3. For each story in the plan:

   If action == "create":
     bmad_create_story({story_key: "0-1-homepage"})
     → Story file created, status = ready-for-dev
     → Follow next_step to develop

   If action == "develop" or "continue":
     bmad_develop_story({story_key: "0-1-homepage"})
     → Read story_content and tasks
     → IMPLEMENT the code in the target project
     → Check off tasks in story file as you go
     → Run tests

     bmad_verify_implementation({story_key: "0-1-homepage"})
     → If ready_for_review: proceed to review
     → If NOT ready: complete remaining tasks/fix tests first

   If action == "review" (or after verify passes):
     bmad_review_story({story_key: "0-1-homepage"})
     → If has_critical_issues:
        - Fix issues from structured_issues array
        - Call bmad_verify_implementation again
        - Re-review
     → If no critical issues: status automatically set to done

4. Repeat until all stories are done
```

### Key Workflow Rules

1. **Always call `bmad_set_project` first** - other tools will fail without it
2. **Follow `next_step` guidance** - every response tells you what to do next
3. **Call `bmad_verify_implementation` before review** - prevents premature reviews
4. **Use `structured_issues` to fix issues** - structured, specific fixes
5. **Re-verify after fixing** - don't skip the verification loop

### Error Handling

All tools return `{success: false, error: "message"}` on failure:
- "No project set. Use bmad_set_project first." - Call `bmad_set_project`
- "Invalid story key format" - Use format `N-N-slug` (e.g., `0-1-homepage`)
- "Story file not found" - Create the story first with `bmad_create_story`
- "Cannot find sprint-status.yaml" - Project structure is wrong

### Known Limitations

**Single-user design:** The MCP server uses global state to track the active project. This means:
- Only one project can be active at a time per server instance
- If the MCP server is shared across multiple Claude conversations, they will share the same project context
- Calling `bmad_set_project` in one conversation affects all conversations using that server instance

This is intentional for simplicity in single-user local development. For multi-user scenarios, run separate MCP server instances.

### Package Structure

```
bmad_mcp/
├── server.py      # MCP server + tool definitions
├── project.py     # Project validation
├── sprint.py      # Sprint status YAML operations
├── llm.py         # LLM CLI wrapper (uses llm CLI for multi-provider)
└── phases/
    ├── create.py  # Story creation via Claude
    ├── develop.py # Returns implementation instructions
    └── review.py  # Code review via Claude Opus
```

## CLI Scripts

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

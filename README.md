# BMAD Autopilot

Automated orchestration for BMAD (Business-driven, Methodical, Agile Development) workflows. Manages the full story lifecycle from backlog to done using LLM-powered story creation, agentic development, and adversarial code review.

## Installation

### 1. Install Dependencies

```bash
# macOS
brew install yq coreutils

# Install llm CLI and plugins
pip install llm
llm install llm-anthropic llm-gemini

# Verify llm is configured with API keys
llm keys set anthropic
llm keys set gemini
```

### 2. Install BMAD Autopilot

```bash
# Clone the repository
git clone https://github.com/yourusername/bmad-autopilot.git
cd bmad-autopilot

# Run setup (installs/verifies dependencies)
./bmad-setup.sh

# Optional: Add to PATH
ln -s "$(pwd)/bmad-autopilot.sh" /usr/local/bin/bmad-autopilot
ln -s "$(pwd)/bmad-phase.sh" /usr/local/bin/bmad-phase
```

### 3. Optional: Install Development Tools

For the development phase, install one of:

```bash
# Option A: Aider (recommended for unattended mode)
pip install aider-chat

# Option B: Claude Code
# Install from https://claude.ai/code
```

## MCP Server (Recommended)

The MCP server lets Claude Code directly orchestrate BMAD workflows.

### Install MCP Server

```bash
# Create virtual environment and install
cd /path/to/bmad-autopilot
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Add to Claude Code
claude mcp add bmad -- /path/to/bmad-autopilot/.venv/bin/bmad-mcp

# Verify it's connected
claude mcp list
```

### MCP Tools

| Tool | Description |
|------|-------------|
| `bmad_set_project` | Set active BMAD project directory |
| `bmad_status` | Get sprint status with story counts |
| `bmad_next` | Get next actionable stories |
| `bmad_create_story` | Generate story from epics |
| `bmad_develop_story` | Get implementation instructions |
| `bmad_verify_implementation` | Check if implementation is ready for review |
| `bmad_review_story` | Run adversarial code review |
| `bmad_update_status` | Update story status |
| `bmad_run_epic` | Get orchestration plan for epic |

### Example Workflow

```
You: "Run epic 0 for ~/Workspace/myproject"

Claude: [Calls bmad_set_project, then bmad_run_epic]
        "Epic 0 has 3 stories. Let me create the first one..."
        [Calls bmad_create_story for 0-1-homepage]
        [Calls bmad_develop_story, reads instructions, implements]
        [Calls bmad_review_story]
        "Review passed. Moving to next story..."
```

---

## CLI Usage

### Full Pipeline (bmad-autopilot)

```bash
# Run in current directory (must be a BMAD project)
bmad-autopilot

# Run against a specific project
bmad-autopilot --project ~/Workspace/myproject

# Process only Epic 0
bmad-autopilot --epic 0

# Run with tmux dashboard
bmad-autopilot --tmux

# Fully unattended mode (auto-accepts all changes)
bmad-autopilot --yolo
```

### Single Phases (bmad-phase)

Run individual phases manually for more control:

```bash
# Check sprint status
bmad-phase status

# See next actionable stories
bmad-phase next

# Create a story from epics
bmad-phase create 0-1-homepage

# Develop a story (launches aider/claude)
bmad-phase develop 0-1-homepage

# Run adversarial code review
bmad-phase review 0-1-homepage

# Specify project
bmad-phase status --project ~/myproject
```

## Project Setup

Your project needs these files:

```
your-project/
├── docs/
│   ├── epics.md                    # Epic definitions
│   └── sprint-artifacts/
│       └── sprint-status.yaml      # Story status tracking
├── ARCHITECTURE.md                 # Optional: architecture context
└── README.md                       # Optional: project context
```

### sprint-status.yaml Format

```yaml
development_status:
  0-1-homepage: backlog
  0-2-navigation: backlog
  1-1-auth-login: backlog
```

### epics.md Format

```markdown
# Epics

## Epic 0: Foundation
- 0-1: Homepage layout
- 0-2: Navigation component

## Epic 1: Authentication
- 1-1: User login
```

## Configuration

Set environment variables to customize models:

```bash
export CLAUDE_MODEL="anthropic/claude-sonnet-4-5"   # Story creation
export AIDER_MODEL="anthropic/claude-sonnet-4-5"   # Development
export REVIEW_MODEL="anthropic/claude-opus-4-0"    # Code review
export LLM_TIMEOUT=300                             # Seconds per LLM call
```

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                      BMAD Autopilot                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   backlog ──► ready-for-dev ──► review ──► done            │
│      │              │             │                         │
│      ▼              ▼             ▼                         │
│   [Claude]      [Aider/        [Claude                      │
│   creates       Claude]        Opus]                        │
│   story         implements     reviews                      │
│                                   │                         │
│                                   ▼                         │
│                           CRITICAL? ──yes──► in-progress    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

1. **Story Creation**: Picks up `backlog` stories, generates detailed implementation guides
2. **Development**: Hands off to aider or claude for implementation
3. **Code Review**: Adversarial review comparing git diff to story requirements
4. **Loop**: Critical issues send story back to development

## Tmux Dashboard

Run with `--tmux` for a live dashboard:

```
┌─────────────────────────────────────┐
│           Main Output               │
├──────────────────┬──────────────────┤
│   Sprint Status  │   Log Tail       │
└──────────────────┴──────────────────┘
```

## License

MIT

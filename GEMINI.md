# BMAD Autopilot Project Context

## Project Overview
BMAD (Business-driven, Methodical, Agile Development) Autopilot is an automation tool designed to orchestrate the full software development lifecycle. It uses LLMs to manage stories from backlog to completion, handling story creation, agentic development (via tools like Aider or Claude), and adversarial code review.

The project provides two primary interfaces:
1.  **MCP Server (`bmad-mcp`)**: A Model Context Protocol server that allows AI assistants (like Claude Code) to directly drive the workflow.
2.  **CLI Scripts**: Bash scripts (`bmad-autopilot.sh`, `bmad-phase.sh`) for manual or automated pipeline execution.

## Architecture & Key Components

### Python Package (`bmad_mcp`)
*   **`bmad_mcp/server.py`**: The entry point for the MCP server. Exposes tools like `bmad_status`, `bmad_create_story`, `bmad_develop_story`, etc.
*   **`bmad_mcp/sprint.py`**: Handles parsing and updating of the `sprint-status.yaml` file.
*   **`bmad_mcp/phases/`**: Contains logic for specific workflow phases (create, develop, review).

### Shell Scripts
*   **`bmad-autopilot.sh`**: The main orchestration script for the CLI workflow.
*   **`bmad-phase.sh`**: Allows running individual phases of the workflow.
*   **`bmad-setup.sh`**: Sets up the environment and verifies dependencies.

### Data files (User Project)
The tool operates on a target project which must contain:
*   `docs/epics.md`: Definitions of Epics and their stories.
*   `docs/sprint-artifacts/sprint-status.yaml`: Tracks the state of each story (`backlog`, `ready-for-dev`, `in-progress`, `review`, `done`).

## Build and Installation

### Prerequisites
*   **Python**: >= 3.10
*   **System Tools**: `yq`, `coreutils` (specifically `gtimeout` on macOS).
*   **LLM CLI**: The `llm` command-line tool with `llm-anthropic` and `llm-gemini` plugins installed and configured.

### Installation
To install the Python package in editable mode:
```bash
pip install -e .
```

To run the setup script:
```bash
./bmad-setup.sh
```

## Usage

### MCP Server
The MCP server is the recommended interface for AI agents. It is started via the `bmad-mcp` command (defined in `pyproject.toml`).
```bash
claude mcp add bmad -- $(which bmad-mcp)
```

### CLI
Run the full autopilot pipeline:
```bash
./bmad-autopilot.sh --project /path/to/project
```

Run a specific phase:
```bash
./bmad-phase.sh next
./bmad-phase.sh create 0-1-homepage
```

## Development Conventions

*   **Testing**: The project uses `pytest`. Run tests with:
    ```bash
    pytest
    ```
*   **Formatting/Linting**: Adhere to standard Python conventions. (No specific linter config found, assume PEP 8).
*   **Environment**: Uses `pyproject.toml` for dependency management.

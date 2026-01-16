# Repository Guidelines

## Project Structure & Module Organization
- `bmad_mcp/`: Python MCP server package (core logic, phases, LLM helpers).
- `bmad_orchestrator.py`: Orchestrator for the BMAD workflow pipeline.
- `bmad-autopilot.sh`, `bmad-phase.sh`, `bmad-setup.sh`: CLI entrypoints and setup scripts.
- `tests/`: Pytest suite (`tests/test_*.py`).
- `docs/`: Design notes and review artifacts.

## Build, Test, and Development Commands
- Install dev environment and editable package:
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -e .[dev]
  ```
- Run tests (quiet mode):
  ```bash
  pytest -q
  ```
- Run CLI pipeline against a BMAD project:
  ```bash
  bmad-autopilot --project ~/Workspace/myproject
  ```
- Run a single phase:
  ```bash
  bmad-phase review 0-1-homepage
  ```

## Coding Style & Naming Conventions
- Python: keep 4-space indentation; follow existing module patterns in `bmad_mcp/`.
- Shell scripts: POSIX-style `bash`/`sh` with `set -euo pipefail` at the top.
- Naming: tests follow `tests/test_<area>.py`; stories use `epic-story-name` format like `0-1-homepage`.
- Formatting/linting: no formatter is mandated; keep diffs minimal and match surrounding style.

## Testing Guidelines
- Framework: `pytest` (declared in `pyproject.toml` under `dev` extras).
- Naming: add tests in `tests/` and use `test_*` functions/classes.
- Coverage: no explicit coverage threshold; focus on new or changed behavior.

## Commit & Pull Request Guidelines
- Commit style follows Conventional Commits (examples in history: `fix(review): ...`, `feat(aider): ...`).
- PRs should include:
  - Clear description of behavior changes.
  - References to relevant issues or epics.
  - Test evidence (`pytest -q` output or notes on what was not run).

## Configuration Tips
- LLM configuration relies on environment variables (examples):
  ```bash
  export CLAUDE_MODEL="anthropic/claude-sonnet-4-5"
  export AIDER_MODEL="anthropic/claude-sonnet-4-5"
  export REVIEW_MODEL="anthropic/claude-opus-4-0"
  ```

# Design Plan: 6-3-design-plan

## 1. Objective
Introduce an explicit plan/execute split for development so each story generates a validated design plan before implementation begins.

## 2. Proposed Changes
### Files to Create
- `bmad_mcp/phases/plan.py`: Orchestrate design plan generation + validation.
- `bmad_mcp/phases/execute.py`: Provide execution instructions that embed the plan.
- `bmad_mcp/planning/__init__.py`: Package exports.
- `bmad_mcp/planning/generator.py`: LLM-backed plan generator.
- `bmad_mcp/planning/validator.py`: LLM-backed architecture validator.
- `bmad_mcp/planning/templates/design-plan.md.j2`: Plan template.

### Files to Modify
- `bmad_mcp/phases/develop.py`: Orchestrate plan + execute when called directly.
- `bmad_mcp/phases/__init__.py`: Export new phase helpers.
- `bmad_mcp/server.py`: Register MCP tools and handlers.
- `bmad_mcp/sprint.py`: Extend statuses to include planning/executing.
- `bmad-phase.sh`: Add plan/execute phases for CLI workflows.
- `bmad-autopilot.sh`: Wire plan/execute into the develop flow.
- `tests/`: Add plan/execute unit tests.

## 3. Detailed Logic
- Plan phase:
  - Load story content.
  - Build context: story, architecture doc, indexed code snippets.
  - Use template-guided LLM prompt to generate `design-plan.md`.
  - Validate plan with LLM against architecture; write `validation-report.md`.
  - Update status to `planning`.
- Execute phase:
  - Require existing plan + passing validation.
  - Provide execution instructions with plan content as primary context.
  - Update status to `executing`.
- Develop phase:
  - Run plan and validation.
  - If validation fails, return planning info only.
  - If validation passes, return execute instructions.

## 4. Architectural Impact
- Adds a planning subsystem that depends on existing LLM wrapper and context retriever.
- Introduces new sprint statuses; existing tooling must tolerate new values.

## 5. Testing Plan
- Unit tests for plan generation + validation outputs (LLM calls mocked).
- Unit tests for execute instructions requiring an existing plan.
- Server tool handler tests for plan/execute responses if feasible.

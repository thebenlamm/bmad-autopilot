# Story 6-3: Explicit "Design Plan" Phase

**Status:** ready-for-dev  
**Epic:** Epic 6 - BMAD Self-Improvement  
**Story ID:** 6-3-design-plan

## User Story

As a **BMAD developer agent**,  
I want **to create and validate a design plan before modifying the codebase**,  
So that **the implementation is architecturaly sound, reviewed for risks, and follows project conventions before code is written.**

## Acceptance Criteria

### AC1: Split Development Phase
```gherkin
Given a story in "ready-for-dev" status
When I start the development phase
Then the process should be split into "Planning" and "Execution" steps
And "Planning" must complete and be validated before "Execution" begins
```

### AC2: Design Plan Artifact Generation
```gherkin
Given I am in the "Planning" step of a story
When the planning process completes
Then a "design-plan.md" file should be created in the story's artifact directory
And the plan should include proposed changes, file modifications, and architectural impact
```

### AC3: Architectural Validation
```gherkin
Given a "design-plan.md" has been generated
When the validation tool runs
Then it should check the plan against "docs/architecture.md" or "ARCHITECTURE_REALITY.md"
And it should identify potential violations or risks
```

### AC4: Implementation Tool Integration
```gherkin
Given a validated "design-plan.md"
When I run the "Execution" step
Then the development agent (Aider/Claude) should receive the design plan as primary context
And the agent should be instructed to strictly follow the plan
```

### AC5: Manual Approval Gate (Optional)
```gherkin
Given a design plan has been generated
When BMAD is running in interactive mode
Then it should pause and request user approval of the "design-plan.md" before proceeding to execution
```

## Tasks

### Task 1: Core Workflow Refactoring
- [ ] Update `bmad_mcp/phases/develop.py` to support split phases
  - [ ] Implement `bmad_plan_implementation` tool
  - [ ] Implement `bmad_execute_implementation` tool
  - [ ] Update `bmad_develop_story` to orchestrate both if run as a single command
- [ ] Modify `bmad-phase.sh` and `bmad-autopilot.sh` to support the new steps
  - [ ] Add `plan` and `execute` subcommands to `develop` or as standalone phases
- [ ] Update `sprint-status.yaml` schema to track "planning" and "executing" sub-states

### Task 2: Design Plan Generator
- [ ] Create `src/bmad/planning/generator.py`
  - [ ] Define the `design-plan.md` template
  - [ ] Implement logic to gather context (story, architecture, current code)
  - [ ] Prompt the LLM to generate a structured implementation plan
- [ ] Implement plan sections:
  - [ ] Proposed File Changes (New/Modified/Deleted)
  - [ ] Key Logic & Algorithms
  - [ ] Data Model Changes
  - [ ] Security Considerations
  - [ ] Test Strategy
  - [ ] Migration Plan (if applicable)

### Task 3: Architectural Validator
- [ ] Create `src/bmad/planning/validator.py`
  - [ ] Implement `ArchitecturalValidator` class
  - [ ] Load architecture documentation as constraints
  - [ ] Use an LLM to compare the `design-plan.md` against architectural constraints
  - [ ] Generate a `validation-report.md` artifact
- [ ] Define common architectural "red flags" (e.g., circular dependencies, bypasses of layers)

### Task 4: Integration with Agents
- [ ] Modify the development agent prompts (Aider/Claude)
  - [ ] Inject the `design-plan.md` content into the initial message
  - [ ] Add strict instructions: "Do not deviate from the design plan without justification"
- [ ] Implement a "Plan vs Reality" check at the end of execution
  - [ ] Verify that the files modified match those in the plan

### Task 5: Interactive Approval Loop
- [ ] Add CLI/MCP support for manual plan approval
  - [ ] Implement `bmad_approve_plan` tool
  - [ ] Update the orchestrator to wait for approval if in interactive mode
  - [ ] Provide a summary of the plan for quick review

### Task 6: Testing
- [ ] Add unit tests for `bmad_plan_implementation`
- [ ] Add unit tests for `bmad_execute_implementation`
- [ ] Add integration tests for the full planning -> execution flow
- [ ] Mock architectural violations to test validator

## Technical Requirements

### File Structure
```
bmad_mcp/
├── phases/
│   ├── develop.py (updated)
│   ├── plan.py (new)
│   └── execute.py (new)
├── planning/
│   ├── __init__.py
│   ├── generator.py
│   ├── validator.py
│   └── templates/
│       └── design-plan.md.j2
└── workflow/
    └── develop_orchestrator.py (new)

docs/sprint-artifacts/
└── {story-id}/
    ├── design-plan.md
    └── validation-report.md
```

### Design Plan Template Structure
```markdown
# Design Plan: {story-id}

## 1. Objective
Brief summary of what this implementation aims to achieve.

## 2. Proposed Changes
### Files to Create
- `path/to/file.py`: Purpose and key components

### Files to Modify
- `path/to/existing_file.py`: Description of changes

## 3. Detailed Logic
- Sequence diagrams or step-by-step logic
- New functions/classes and their signatures

## 4. Architectural Impact
- How this fits into the existing layers
- Impact on performance/security/maintainability

## 5. Testing Plan
- Unit tests to add
- Integration scenarios
- Edge cases to cover
```

## Definition of Done
- [ ] `bmad_plan_implementation` and `bmad_execute_implementation` tools are functional
- [ ] `design-plan.md` is generated and saved as an artifact
- [ ] Architectural validator identifies risks in plans
- [ ] Development agents use the plan during execution
- [ ] Tests cover both success and failure (invalid plan) cases
- [ ] Documentation updated to reflect the new workflow

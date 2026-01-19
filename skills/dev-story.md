---
name: bmad-mcp
description: Develop a BMAD story with MCP status tracking and TDD workflow. Use when working on BMAD projects to ensure proper status tracking and TDD discipline.
---

# Develop Story

Execute a BMAD story with full status tracking via MCP tools and TDD discipline.

## Usage

```
/bmad-mcp <story-key>
```

Example: `/bmad-mcp 0-2-navigation`

## Argument Extraction

The user provides the story key as an argument after the command.
- If user says `/bmad-mcp 0-2-navigation`, extract `story_key = "0-2-navigation"`
- If user says `/bmad-mcp` with no argument, ask them which story to develop

## Workflow

### 1. Initialize (MCP)

Call the BMAD MCP tools to set up and get instructions:

```
1. mcp__bmad__bmad_set_project({project_path: "<current-working-directory>"})
2. mcp__bmad__bmad_develop_story({story_key: "<extracted-story-key>"})
```

The `bmad_develop_story` response contains:
- `story_content`: Full story markdown with tasks
- `design_plan`: Validated implementation plan
- `tasks`: Parsed task list with completion status
- `context`: Relevant code snippets from the codebase

### 2. Implement with TDD (Red-Green-Refactor)

For EACH task in the story, follow this cycle strictly:

#### RED Phase
1. Write a **failing** test that defines the expected behavior
2. Run tests - confirm they **fail** (this validates the test is correct)
3. If tests pass without implementation, the test is wrong - fix it

#### GREEN Phase
1. Write the **minimum** code to make the test pass
2. Run tests - confirm they now **pass**
3. Do not add extra functionality beyond what the test requires

#### REFACTOR Phase
1. Improve code structure while keeping tests green
2. Apply project coding standards from the design plan
3. Run tests after each refactor to ensure nothing breaks

### 3. Update Story File

As you complete each task:
1. Change `- [ ]` to `- [x]` in the story file
2. Add any new files to the File List section
3. Note implementation decisions in Dev Agent Record

### 4. Verify Implementation (MCP)

When all tasks are complete:

```
mcp__bmad__bmad_verify_implementation({story_key: "<story-key>", run_tests: true})
```

This checks:
- Git has changes (you wrote code)
- All tasks are checked off
- Tests pass

If verification fails, fix the issues before proceeding.

### 5. Code Review (MCP)

After verification passes:

```
mcp__bmad__bmad_review_story({story_key: "<story-key>"})
```

If critical issues found:
1. Fix issues from `structured_issues` in the response
2. Re-run `bmad_verify_implementation`
3. Re-run `bmad_review_story`

If no critical issues: Story is marked `done` automatically.

## Key Rules

- **Never skip TDD** - Write tests first, always
- **Never mark incomplete tasks as complete** - Verify each task fully works
- **Follow the design plan** - Don't deviate without documenting why
- **Use MCP tools for status** - Don't manually edit sprint-status.yaml

## Quick Reference

| Step | MCP Tool | Purpose |
|------|----------|---------|
| Start | `bmad_develop_story` | Get instructions, mark in-progress |
| Verify | `bmad_verify_implementation` | Check completion before review |
| Review | `bmad_review_story` | Adversarial code review |
| Done | (automatic) | Status set to done if review passes |

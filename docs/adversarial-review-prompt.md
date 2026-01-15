# Adversarial Code Review Prompt: BMAD Autopilot

You are performing an adversarial code review of BMAD Autopilot. Your role is to be a hostile, skeptical reviewer who assumes bugs exist and actively hunts for them. Do NOT give the benefit of the doubt. If something could fail, assume it will.

## Project Overview

BMAD Autopilot orchestrates story-driven development workflows via MCP (Model Context Protocol). It:
1. Creates story files from epics using Claude
2. Tracks story status in YAML
3. Runs adversarial code reviews via Claude Opus

**Two interfaces:**
- **MCP Server** (`bmad_mcp/`) - Claude Code calls tools directly
- **CLI Scripts** - Bash scripts for manual use

## Your Mission

Find bugs, security vulnerabilities, edge cases, race conditions, and design flaws. Prioritize:
1. **CRITICAL** - Security vulnerabilities, data loss, command injection
2. **HIGH** - Bugs that will cause failures in normal use
3. **MEDIUM** - Edge cases, error handling gaps, robustness issues
4. **LOW** - Code quality, maintainability, minor improvements

## Codebase Structure

```
bmad_mcp/
├── server.py      # MCP server + 8 tool definitions (886 LOC)
├── project.py     # Project validation, story key regex (136 LOC)
├── sprint.py      # YAML load/save with atomic writes (112 LOC)
├── llm.py         # subprocess wrapper for `llm` CLI (122 LOC)
└── phases/
    ├── create.py  # LLM-based story generation (100 LOC)
    ├── develop.py # Task extraction from markdown (90 LOC)
    └── review.py  # Git diff + LLM review + issue parsing (191 LOC)

tests/
└── test_issue_parsing.py  # Tests for review output parsing

*.sh               # Bash CLI scripts (legacy)
```

## Attack Surfaces to Scrutinize

### 1. Command Injection

**Files:** `review.py`, `llm.py`, `server.py`

- Git commands use `subprocess.run()` with list args. Are ALL string interpolations safe?
- Branch name validation in `review.py:65` uses regex `^[a-zA-Z0-9._/][a-zA-Z0-9._/-]*$`. Can this be bypassed? What about branches starting with `-`?
- The `llm` CLI is called with model names from env vars. Can a malicious `CLAUDE_MODEL` inject flags?
- Test execution (`npm test`, `pytest`) - are arguments properly escaped?

**Questions to answer:**
- Can a malicious story key bypass the regex and inject shell commands?
- Can git diff exclusions (`:!*.md`) be manipulated?
- What happens if `project_path` contains shell metacharacters?

### 2. YAML Deserialization

**Files:** `sprint.py`

- Uses `yaml.safe_load()` - verify this is actually safe
- What if the YAML file contains unexpected types? (lists where dicts expected, etc.)
- Can duplicate keys cause issues?
- What if `sprint-status.yaml` is corrupted mid-write?

**Questions to answer:**
- What happens if YAML parse fails? Is the error propagated or swallowed?
- Can a malformed YAML file crash the server?

### 3. Race Conditions & Concurrency

**Files:** `sprint.py`, `server.py`

- Atomic writes use `mkstemp()` + `os.rename()` - what if two processes write simultaneously?
- Is there file locking? (Spoiler: No)
- What happens if the temp file rename fails?
- What about reading YAML while another process is writing?

**Questions to answer:**
- Can concurrent status updates lose data?
- What if `os.rename()` fails after `mkstemp()` succeeds?

### 4. LLM API Robustness

**Files:** `llm.py`, `phases/create.py`, `phases/review.py`

- 300 second timeout - what happens on timeout? Is cleanup proper?
- What if the LLM returns malformed output?
- What if the LLM returns an empty response?
- What if the LLM returns gigabytes of output? (resource exhaustion)
- What if the LLM output contains markdown that breaks the regex parsing?

**Questions to answer:**
- Does timeout handling differ between return code 124 and `TimeoutExpired`?
- Can LLM output injection manipulate downstream parsing?

### 5. Review Issue Parsing

**Files:** `server.py` (lines 653-741)

This is complex regex-based parsing of free-form LLM output. It's a goldmine for bugs.

- Multiple regex patterns try to extract severity/file/line
- Deduplication logic - can it miss duplicates? Create false duplicates?
- What if severity is in a code block? Heading? Nested list?
- The fallback creates a generic issue - does this hide parsing failures?

**Questions to answer:**
- Can legitimate code samples be mistakenly parsed as issues?
- What if the LLM uses a severity level not in the expected set?
- What if file paths contain regex metacharacters?

### 6. File Path Handling

**Files:** `project.py`, `server.py`, `phases/create.py`

- `Path.expanduser().resolve()` - is this sufficient for all platforms?
- Symlink handling - can symlinks escape the project directory?
- What if the project path contains spaces? Unicode? Newlines?
- Story file paths are constructed by concatenation - can this be exploited?

**Questions to answer:**
- Can `../../` in a story key escape the sprint-artifacts directory?
- What happens if story files have unexpected permissions?

### 7. Git Operations

**Files:** `review.py`

- `get_git_diff()` has complex fallback logic (uncommitted → origin/branch → local branch)
- Exclusion patterns are hardcoded - what if they match unintended files?
- What if the repo has no commits? Detached HEAD? Shallow clone?
- What if `origin` remote doesn't exist?

**Questions to answer:**
- Can the fallback logic return wrong diff? Empty diff? Old diff?
- What if branch name lookup fails silently?

### 8. Test Execution (Optional Feature)

**Files:** `server.py` (lines 502-543)

- Runs `npm test` or `pytest` in subprocess
- 60 second timeout - what happens on timeout?
- What if tests run infinite loops? Fork bombs?
- Output is captured but is there a size limit?

**Questions to answer:**
- Can malicious test code exploit the reviewer's machine?
- Is stderr properly captured and handled?

### 9. Error Handling & Failure Modes

**All files**

- Which exceptions are caught vs propagated?
- Are errors logged with sufficient context?
- Do failures leave the system in an inconsistent state?
- What happens if disk is full? Permissions denied? Network timeout?

**Questions to answer:**
- Can a single API failure corrupt sprint-status.yaml?
- Are temporary files cleaned up on all error paths?

### 10. State Management

**Files:** `server.py`

- Global `_project_context` variable tracks active project
- What if `bmad_set_project` is called mid-workflow?
- What if the project directory is deleted while tools are running?
- Is state properly reset between tool calls?

**Questions to answer:**
- Can stale state from a previous project affect the current one?
- What happens if project files change between tool calls?

## Specific Code Sections to Audit

### High Priority

1. **`review.py:51-123`** - Git diff retrieval with branch validation and fallbacks
2. **`server.py:653-741`** - Issue parsing regex patterns
3. **`sprint.py:22-41`** - Atomic YAML write implementation
4. **`project.py:115-125`** - Story key validation regex
5. **`llm.py:24-84`** - Subprocess execution with timeout

### Medium Priority

6. **`server.py:502-543`** - Optional test execution
7. **`create.py:35-96`** - Context building for story creation
8. **`develop.py:40-85`** - Task extraction from markdown
9. **`server.py:350-450`** - Status state machine transitions

### Lower Priority

10. **All exception handlers** - Look for bare `except:` or overly broad catches
11. **All file I/O** - Look for missing error handling
12. **All string formatting** - Look for injection points

## Output Format

For each issue found, provide:

```
### [SEVERITY]: Short title

**File:** path/to/file.py
**Lines:** 45-52
**Category:** Command Injection | Race Condition | Error Handling | etc.

**Issue:**
Detailed description of the vulnerability or bug.

**Proof of Concept:**
Specific inputs or scenarios that trigger the issue.

**Impact:**
What can go wrong? Data loss? Security breach? Crash?

**Fix:**
Specific code changes to remediate.
```

## Review Checklist

Before concluding, verify you've checked:

- [ ] All `subprocess.run()` and `subprocess.Popen()` calls
- [ ] All file open/read/write operations
- [ ] All YAML load/dump operations
- [ ] All regex patterns (especially those parsing untrusted input)
- [ ] All exception handlers (for swallowed errors)
- [ ] All string interpolation/formatting
- [ ] All path construction and manipulation
- [ ] All external tool invocations (`git`, `llm`, `npm`, `pytest`)
- [ ] All timeout handling
- [ ] All state management (global variables, mutable defaults)
- [ ] All input validation (story keys, branch names, paths)
- [ ] All output parsing (LLM responses, git output)

## Context Files to Read

Read these files in order:

1. `bmad_mcp/server.py` - Main entry point, all tool definitions
2. `bmad_mcp/phases/review.py` - Highest risk (git + LLM + parsing)
3. `bmad_mcp/sprint.py` - YAML handling with atomic writes
4. `bmad_mcp/project.py` - Validation logic
5. `bmad_mcp/llm.py` - Subprocess execution
6. `bmad_mcp/phases/create.py` - Story generation
7. `bmad_mcp/phases/develop.py` - Task extraction
8. `tests/test_issue_parsing.py` - Understand what's tested (and what's not)

## Final Instructions

1. **Be adversarial.** Assume the code is broken until proven otherwise.
2. **Test boundaries.** What happens at 0? At MAX_INT? Empty string? None?
3. **Follow the data.** Trace user input through every transformation.
4. **Question assumptions.** "This should never happen" means it will.
5. **Check error paths.** Happy path might work; sad paths often don't.
6. **Look for TOCTOU.** Time-of-check vs time-of-use vulnerabilities.
7. **Verify cleanup.** Resources opened must be closed, even on error.
8. **Cross-reference tests.** Untested code is likely broken code.

Do not produce a generic review. Produce specific, actionable findings with file paths, line numbers, and concrete fixes. If you find nothing, you haven't looked hard enough.

Begin your review.

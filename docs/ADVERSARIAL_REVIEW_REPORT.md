# Adversarial Code Review Report: BMAD Autopilot

**Date:** 2026-01-15
**Reviewer:** Gemini (Adversarial Agent)
**Target:** BMAD Autopilot Codebase

## Executive Summary

The review identified **2 CRITICAL** and **1 HIGH** severity issues that compromise data integrity and the reliability of the review process. The most significant finding is a potential data loss scenario in `sprint-status.yaml` handling, where a transient read error or malformed file could lead to the complete erasure of sprint data. Additionally, the code review phase fails "open" when git commands fail, potentially allowing unreviewed code to bypass checks.

## Findings

### [CRITICAL]: Sprint Status Data Loss on Read Error

**File:** `bmad_mcp/sprint.py`
**Lines:** 33-36, 100-112
**Category:** Error Handling / Data Integrity

**Issue:**
The `load_sprint_status` function swallows `yaml.YAMLError` (and `FileNotFoundError`) and returns an empty dictionary `{}`. The `update_story_status` function then takes this empty dictionary, adds the single story being updated, and **overwrites** the `sprint-status.yaml` file with just that single story.

If `sprint-status.yaml` has a syntax error (e.g., from a manual edit) or a transient read failure, the entire sprint history will be wiped out when the next tool update occurs.

**Proof of Concept:**
1. Manually edit `sprint-status.yaml` and introduce a syntax error (e.g., bad indentation).
2. Run `bmad_update_status(story_key="0-1-new", status="ready-for-dev")`.
3. `load_sprint_status` fails to parse, catches exception, returns `{}`.
4. `update_story_status` adds "0-1-new".
5. `save_sprint_status` writes the new dict to disk.
6. **Result:** The file now contains *only* "0-1-new". All previous stories are lost.

**Impact:**
Complete loss of project tracking data. Irrecoverable unless backed up by git (which might not have the latest state).

**Fix:**
Propagate `yaml.YAMLError` instead of swallowing it. Do not proceed with a write operation if the read failed due to data corruption.

```python
def load_sprint_status(path: Path) -> dict:
    """Load sprint-status.yaml."""
    try:
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}
    # Do not catch YAMLError here, let it crash the tool rather than corrupt data
```

### [CRITICAL]: Deadlock/Hang Risk in LLM Subprocess Write

**File:** `bmad_mcp/llm.py`
**Lines:** 77-80
**Category:** Concurrency / Denial of Service

**Issue:**
The `call_llm` function writes context to the subprocess stdin using `process.stdin.write(context)`. If `context` is larger than the OS pipe buffer (typically 64KB) and the subprocess does not read it immediately (or crashes before reading), `stdin.write` will block indefinitely. While `process.wait` has a timeout, it is unreachable if `write` blocks.

Although the `llm` CLI reads stdin, relying on the subprocess behavior for control flow is risky. If the `llm` tool changes behavior or fails early, the server hangs.

**Impact:**
The MCP server could hang indefinitely on large contexts, requiring a hard restart.

**Fix:**
Use `process.communicate(input=context, timeout=timeout)` instead of manual write/wait. It handles buffering and timeouts correctly.

```python
# Replace manual stdin write and wait with:
stdout, stderr = process.communicate(input=context, timeout=timeout + 10)
```

### [HIGH]: Code Review Fails Open (Bypass)

**File:** `bmad_mcp/phases/review.py`
**Lines:** 88-100, 245-255
**Category:** Logic Flaw

**Issue:**
In `get_git_diff`, if the git commands fail (e.g., `git diff` returns non-zero exit code due to missing upstream branch or git configuration issues), the function returns a string: `"No diff available..."`.

In `review_story`, this error string is passed as the `context` to the LLM. The LLM, seeing no code, will likely report "No issues found". The `structured_issues` list will be empty, `has_critical_issues` will be `False`, and the story will be marked as `done`.

This means a broken git configuration or missing remote branch causes code to effectively **bypass** the review process.

**Impact:**
Unverified, potentially buggy or malicious code is marked as "done" and merged without actual review.

**Fix:**
`get_git_diff` should raise an exception or return `None` on failure. `review_story` must handle this failure explicitly and abort the review (or mark it as failed), rather than proceeding with a "successful" empty review.

### [MEDIUM]: Fragile Review Parsing Fallback

**File:** `bmad_mcp/phases/review.py`
**Lines:** 198-208
**Category:** Logic Flaw

**Issue:**
The parser attempts to fallback to a generic "CRITICAL" issue if the structured parsing fails but the word "CRITICAL" appears in the text. It tries to avoid false positives by checking `if "NO CRITICAL ISSUES" not in review_content.upper()`.

This is brittle. Phrases like "No critical vulnerabilities found" or "Absence of critical bugs" would fail this check (as they don't contain the exact string "NO CRITICAL ISSUES") but trigger the "CRITICAL" detection, causing a false positive. Conversely, a typo in the LLM output could bypass detection.

**Impact:**
False positives block development (annoyance). False negatives (rare but possible with weird phrasing) allow critical issues to pass.

**Fix:**
Prompt the LLM to output a specific, machine-readable JSON block or strict separator that is less ambiguous than natural language parsing.

### [LOW]: Unnecessary Lock File Truncation

**File:** `bmad_mcp/sprint.py`
**Lines:** 19
**Category:** Efficiency

**Issue:**
The lock context manager opens the lock file with mode `'w'`.
```python
with open(lock_path, 'w') as f:
```
This truncates the file every time a lock is acquired. While harmless for correctness, it causes unnecessary I/O metadata updates. Mode `'a'` or `'r+'` (if exists) would be cleaner.

**Fix:**
Use `'a'` (append) or checks if file exists to avoid truncation.

## Conclusion

The codebase is generally well-structured but has significant gaps in error handling that prioritize "keeping running" over data integrity and security. The "fail-open" nature of the review process and the data-destroying YAML handling are the most urgent fixes required.

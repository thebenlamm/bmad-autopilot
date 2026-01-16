```markdown
# Story 6-1: Automated Remediation Loop (Auto-Fix)

**Status:** ready-for-dev  
**Epic:** Epic 6 - BMAD Self-Improvement  
**Story ID:** 6-1-auto-fix

## User Story

As a **developer using BMAD**  
I want **an automated tool that can apply fixes for issues found during code review**  
So that **I can eliminate manual rework cycles and close the feedback loop between review and development automatically**

## Acceptance Criteria

### AC1: Auto-Fix Tool Registration
```gherkin
Given I have initialized a BMAD workspace
When I run "bmad --list-tools"
Then I should see "bmad_auto_fix" in the available tools list
And the tool description should explain its automated remediation purpose
```

### AC2: Parse Review Issues
```gherkin
Given a code review has been completed with structured issues
When I invoke bmad_auto_fix with a story ID
Then the tool should parse the review.md file
And extract all structured issues with severity, file, and description
And categorize issues as auto-fixable or manual
```

### AC3: Apply Automated Fixes
```gherkin
Given structured issues have been identified as auto-fixable
When the auto-fix engine processes the issues
Then it should apply fixes for common patterns (formatting, imports, types)
And preserve existing code functionality
And track which issues were successfully fixed
```

### AC4: Re-run Validation
```gherkin
Given fixes have been applied to the codebase
When the auto-fix tool completes its changes
Then it should automatically re-run the test suite
And regenerate the review report
And update the story status if all issues are resolved
```

### AC5: Generate Fix Report
```gherkin
Given the auto-fix cycle has completed
When I check the story artifacts
Then there should be an "auto-fix-report.md" file
And it should list all attempted fixes with success/failure status
And provide a summary of remaining manual issues
```

## Tasks

### Task 1: Tool Registration and Setup
- [x] Create `src/bmad/tools/auto_fix.py` with tool definition (adapted: in bmad_mcp/server.py)
  - [x] Define `bmad_auto_fix` tool metadata (name, description, parameters)
  - [x] Add `story_id` parameter (required) - implemented as story_key
  - [x] Add `dry_run` boolean parameter (optional, default: false)
  - [ ] Add `fix_types` array parameter (optional, default: all)
- [x] Register tool in `src/bmad/tools/__init__.py` (adapted: in server.py)
- [x] Add tool to MCP server's available tools list
- [ ] Create configuration schema for auto-fix rules

### Task 2: Review Issue Parser
- [x] Implement `ReviewIssueParser` class in `src/bmad/auto_fix/parser.py` (adapted: bmad_mcp/auto_fix/parser.py)
  - [x] Parse markdown review files for structured issue blocks
  - [x] Extract issue metadata (severity, file, line, type, description)
  - [x] Categorize issues by fixability (auto, semi-auto, manual)
  - [ ] Build issue dependency graph (if fix order matters)
- [x] Create issue data models in `src/bmad/auto_fix/models.py` (adapted: bmad_mcp/auto_fix/models.py)
  - [x] `Issue` class with severity, location, description, fix_type
  - [x] `FixResult` class with status, changes, messages
  - [x] `AutoFixReport` class for aggregated results
- [x] Add unit tests for parser in `tests/unit/auto_fix/test_parser.py` (adapted: tests/test_auto_fix.py)
  - [x] Test parsing various review formats
  - [x] Test edge cases (malformed issues, missing data)
  - [x] Test issue categorization logic

### Task 3: Fix Strategy Engine
- [x] Create `FixStrategyEngine` in `src/bmad/auto_fix/engine.py` (adapted: bmad_mcp/auto_fix/engine.py)
  - [x] Implement strategy pattern for different fix types
  - [ ] Add priority queue for fix execution order
  - [ ] Implement rollback mechanism for failed fixes
  - [x] Add dry-run mode that simulates fixes without applying
- [x] Implement fix strategies in `src/bmad/auto_fix/strategies/` (adapted: bmad_mcp/auto_fix/strategies/)
  - [x] `FormattingStrategy` - Apply code formatting (black, isort)
  - [ ] `ImportStrategy` - Fix missing/unused imports
  - [ ] `TypeHintStrategy` - Add missing type annotations
  - [ ] `DocstringStrategy` - Fix docstring format issues
  - [ ] `NamingStrategy` - Fix naming convention violations
- [x] Create abstract base class `FixStrategy` with interface (bmad_mcp/auto_fix/strategies/base.py)
  - [x] `can_fix(issue)` - Determine if strategy handles this issue
  - [x] `apply_fix(issue, content)` - Apply fix and return modified content
  - [x] `validate_fix(issue, old_content, new_content)` - Verify fix correctness

### Task 4: Code Modification System
- [x] Implement `CodeModifier` in `src/bmad/auto_fix/modifier.py`
  - [x] Safe file read/write with backup creation
  - [ ] AST-based code modification for structural changes
  - [x] Line-based modification for simple text changes
  - [x] Track all modifications for rollback capability
- [x] Create `BackupManager` class
  - [x] Create timestamped backups before modifications
  - [x] Implement rollback functionality
  - [x] Clean up old backups (configurable retention)
- [ ] Add file conflict detection
  - [x] Detect if files changed since review (SafetyGuard)
  - [ ] Warn about potential merge conflicts
  - [ ] Skip files with conflicts in non-dry-run mode

### Task 5: Validation and Re-Testing
- [x] Create `ValidationOrchestrator` in `src/bmad/auto_fix/validator.py`
  - [x] Re-run test suite after fixes applied
  - [ ] Parse test results and compare with previous run
  - [ ] Trigger code review regeneration
  - [ ] Update story status if all issues resolved
- [ ] Implement incremental testing
  - [x] Only re-run tests for modified files (pytest support added)
  - [ ] Fall back to full suite if incremental fails
  - [ ] Cache test results for performance
- [ ] Add fix verification
  - [ ] Confirm issue no longer appears in new review
  - [ ] Ensure no new issues introduced
  - [x] Validate code still passes all tests

### Task 6: Reporting System
- [x] Create `ReportGenerator` in `src/bmad/auto_fix/reporter.py`
  - [x] Generate `auto-fix-report.md` with fix summary
  - [x] Include before/after diffs for each fix
  - [x] List remaining manual issues
  - [x] Provide statistics (fix rate, time saved, etc.)
- [ ] Implement report templates in `src/bmad/templates/auto_fix/`
  - [ ] `report.md.j2` - Main report template
  - [ ] `fix_summary.md.j2` - Per-file fix summary
  - [ ] `manual_issues.md.j2` - Remaining issues list
- [ ] Add report output formats
  - [x] Markdown (default)
  - [ ] JSON (for programmatic access)
  - [ ] HTML (for web viewing)

### Task 7: Integration with BMAD Workflow
- [x] Update `StoryManager` in `src/bmad/workflow/story_manager.py` (Implemented in server.py)
  - [x] Add auto-fix as optional step after review
  - [ ] Track auto-fix attempts in story metadata
  - [ ] Prevent infinite auto-fix loops (max attempts)
- [ ] Modify review workflow in `src/bmad/workflow/review.py`
  - [ ] Suggest auto-fix when fixable issues found
  - [ ] Provide command to trigger auto-fix
  - [ ] Link to auto-fix report in review output
- [ ] Update story status transitions
  - [ ] Add "auto-fixing" status
  - [ ] Transition from "in-review" → "auto-fixing" → "in-review"
  - [ ] Transition to "ready-for-merge" if all issues resolved

### Task 8: Configuration and Safety
- [x] Create `auto_fix_config.yaml` schema (Implemented via config.py)
  - [x] Enabled fix strategies (allow/deny list)
  - [x] Max auto-fix attempts per story
  - [x] Backup retention policy
  - [x] File patterns to exclude from auto-fix
- [x] Implement safety guards in `src/bmad/auto_fix/safety.py`
  - [x] Require clean git working directory
  - [ ] Create git commits for each fix attempt
  - [ ] Limit file size for AST-based modifications
  - [x] Timeout for long-running fixes (via subprocess)
- [ ] Add user confirmation prompts
  - [x] Show planned fixes before applying (unless --yes flag) (Dry Run supported)
  - [ ] Confirm rollback if tests fail
  - [ ] Warn about high-risk modifications

### Task 9: Testing
- [x] Unit tests in `tests/unit/auto_fix/`
  - [x] `test_parser.py` - Review parsing logic
  - [x] `test_engine.py` - Fix strategy engine
  - [x] `test_strategies.py` - Each fix strategy
  - [x] `test_modifier.py` - Code modification logic
  - [x] `test_reporter.py` - Report generation
- [ ] Integration tests in `tests/integration/auto_fix/`
  - [ ] `test_full_cycle.py` - End-to-end auto-fix workflow
  - [ ] `test_rollback.py` - Rollback on failure
  - [ ] `test_multi_file.py` - Fixes across multiple files
  - [ ] `test_edge_cases.py` - Boundary conditions
- [ ] Create test fixtures
  - [ ] Sample review.md files with various issue types
  - [ ] Sample code files with known issues
  - [ ] Expected fix outputs
  - [ ] Mock test results

### Task 10: Documentation
- [ ] Create `docs/auto-fix.md` user guide
  - [ ] Overview of auto-fix capabilities
  - [ ] Usage examples and common scenarios
  - [ ] Configuration options
  - [ ] Troubleshooting guide
- [ ] Update `docs/workflow.md` to include auto-fix step
- [ ] Add inline code documentation
  - [ ] Docstrings for all public classes and methods
  - [ ] Type hints for all functions
  - [ ] Comments for complex logic
- [ ] Create `examples/auto-fix/` directory
  - [ ] Example review with fixable issues
  - [ ] Sample auto-fix report
  - [ ] Configuration examples

## Technical Requirements

### File Structure
```
src/bmad/
├── tools/
│   ├── __init__.py (register auto_fix tool)
│   └── auto_fix.py (tool definition)
├── auto_fix/
│   ├── __init__.py
│   ├── models.py (data models)
│   ├── parser.py (ReviewIssueParser)
│   ├── engine.py (FixStrategyEngine)
│   ├── modifier.py (CodeModifier, BackupManager)
│   ├── validator.py (ValidationOrchestrator)
│   ├── reporter.py (ReportGenerator)
│   ├── safety.py (safety guards)
│   └── strategies/
│       ├── __init__.py
│       ├── base.py (FixStrategy ABC)
│       ├── formatting.py (FormattingStrategy)
│       ├── imports.py (ImportStrategy)
│       ├── types.py (TypeHintStrategy)
│       ├── docstrings.py (DocstringStrategy)
│       └── naming.py (NamingStrategy)
├── templates/
│   └── auto_fix/
│       ├── report.md.j2
│       ├── fix_summary.md.j2
│       └── manual_issues.md.j2
└── workflow/
    ├── story_manager.py (updated)
    └── review.py (updated)

tests/
├── unit/
│   └── auto_fix/
│       ├── test_parser.py
│       ├── test_engine.py
│       ├── test_strategies.py
│       ├── test_modifier.py
│       └── test_reporter.py
├── integration/
│   └── auto_fix/
│       ├── test_full_cycle.py
│       ├── test_rollback.py
│       ├── test_multi_file.py
│       └── test_edge_cases.py
└── fixtures/
    └── auto_fix/
        ├── reviews/
        ├── code_samples/
        └── expected_outputs/

docs/
├── auto-fix.md
└── workflow.md (updated)

examples/
└── auto-fix/
    ├── sample-review.md
    ├── sample-report.md
    └── config-examples.yaml

config/
└── auto_fix_config.yaml
```

### Dependencies
- **AST Manipulation**: `libcst` or `ast` (stdlib) for code transformations
- **Code Formatting**: `black`, `isort` for formatting fixes
- **Type Checking**: `mypy` for type-related fixes
- **Testing**: `pytest` for re-running tests
- **Git Integration**: `gitpython` for commit/rollback operations
- **Diff Generation**: `difflib` (stdlib) for change reports
- **Template Rendering**: `jinja2` for report generation

### Key Interfaces

#### Tool Input Schema
```python
{
    "story_id": "string (required)",
    "dry_run": "boolean (optional, default: false)",
    "fix_types": "array of string (optional, default: all)",
    "auto_commit": "boolean (optional, default: true)",
    "max_attempts": "integer (optional, default: 3)"
}
```

#### Tool Output Schema
```python
{
    "success": "boolean",
    "fixes_applied": "integer",
    "fixes_failed": "integer",
    "manual_issues": "integer",
    "report_path": "string",
    "review_passed": "boolean",
    "message": "string"
}
```

#### Issue Model
```python
@dataclass
class Issue:
    severity: str  # critical, major, minor
    file_path: str
    line_number: Optional[int]
    issue_type: str  # formatting, import, type, docstring, naming
    description: str
    fix_type: str  # auto, semi-auto, manual
    raw_text: str
```

#### Fix Result Model
```python
@dataclass
class FixResult:
    issue: Issue
    status: str  # success, failed, skipped
    changes: List[str]  # list of changes made
    error_message: Optional[str]
    time_taken: float
```

### Configuration Schema
```yaml
auto_fix:
  enabled: true
  max_attempts: 3
  backup_retention_days: 7
  
  strategies:
    formatting:
      enabled: true
      tools: [black, isort]
    imports:
      enabled: true
      add_missing: true
      remove_unused: true
    types:
      enabled: true
      inference_only: true  # only add obvious types
    docstrings:
      enabled: true
      style: google
    naming:
      enabled: false  # more risky, disabled by default
  
  safety:
    require_clean_git: true
    auto_commit: true
    commit_message_prefix: "autofix:"
    max_file_size_kb: 500
    timeout_seconds: 300
  
  exclusions:
    paths:
      - "tests/fixtures/*"
      - "*.min.js"
      - "vendor/*"
    patterns:
      - "# autofix: skip"
```

## Testing Requirements

### Unit Test Coverage
- [ ] Minimum 90% code coverage for auto_fix module
- [ ] All fix strategies individually tested
- [ ] Parser handles malformed input gracefully
- [ ] Modifier preserves code semantics
- [ ] Reporter generates valid markdown

### Integration Test Scenarios
1. **Happy Path**: Review → Auto-Fix → Tests Pass → Review Pass
2. **Partial Fix**: Some issues fixed, some remain manual
3. **Fix Introduces Error**: Auto-rollback triggered
4. **Dirty Git State**: Tool refuses to run
5. **Concurrent Modifications**: File changed during fix
6. **Max Attempts Reached**: Tool stops after limit
7. **Dry Run Mode**: No actual changes made
8. **Large Codebase**: Performance with many files

### Performance Targets
- Parse review file: < 100ms
- Apply single fix: < 500ms per file
- Full auto-fix cycle (10 issues): < 30 seconds
- Report generation: < 1 second

### Error Scenarios to Handle
- Review file not found
- Malformed review markdown
- File permissions errors
- Git conflicts during fix
- Test suite failures after fix
- Timeout on long-running fix
- Out of disk space for backups
- Invalid fix strategy configuration

## Definition of Done
- [ ] All tasks completed and checked off
- [ ] Unit tests pass with >90% coverage
- [ ] Integration tests pass for all scenarios
- [ ] Documentation complete and reviewed
- [ ] Tool registered and accessible via MCP
- [ ] Configuration schema validated
- [ ] Performance targets met
- [ ] Code review completed
- [ ] Example workflows documented
- [ ] Safety guards tested and verified
- [ ] Rollback mechanism proven reliable
- [ ] Report templates render correctly
- [ ] Tool works in both dry-run and live modes

## Notes
- Start with conservative fix strategies (formatting, imports)
- Add more aggressive strategies (naming, refactoring) in future iterations
- Consider adding ML-based fix suggestions in Epic 7
- Integration with 6-2 (RAG) could provide better context for fixes
- Monitor auto-fix success rates to improve strategies over time
```

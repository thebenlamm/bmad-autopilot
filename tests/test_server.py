"""Tests for MCP server functionality."""

import pytest

from bmad_mcp.phases.review import parse_review_issues
from bmad_mcp.project import validate_story_key


class TestParseReviewIssues:
    """Test review issue parsing from LLM output."""

    def test_parse_bold_severity(self):
        """Parse **CRITICAL** style markers."""
        review = """
## Issues Found

**CRITICAL**: SQL injection in `src/db.py:42`
The query uses string concatenation.
Fix: Use parameterized queries.

**HIGH**: Missing null check in `src/api.py:15`
Could cause NullPointerException.
"""
        issues = parse_review_issues(review)
        assert len(issues) >= 2

        critical = [i for i in issues if i["severity"] == "CRITICAL"]
        assert len(critical) >= 1
        assert "SQL injection" in critical[0]["problem"] or "SQL injection" in critical[0].get("full_context", "")

    def test_parse_extracts_file_path(self):
        """Extract file paths from review."""
        review = """
**MEDIUM**: Missing error handling in `src/handlers/auth.py:123`
Should wrap in try-catch.
"""
        issues = parse_review_issues(review)
        assert len(issues) >= 1
        # File should be extracted
        assert any(i.get("file") for i in issues)

    def test_parse_extracts_line_number(self):
        """Extract line numbers when present."""
        review = """
**LOW**: Style issue in `utils.py:42`
Consider using const instead of let.
"""
        issues = parse_review_issues(review)
        file_issues = [i for i in issues if i.get("file")]
        if file_issues:
            assert any(i.get("line") == 42 for i in file_issues)

    def test_no_fallback_for_unstructured_review(self):
        """Do not create issues when no structured format is found."""
        review = """
This code has some problems.
There's a critical security issue.
Please fix it.
"""
        issues = parse_review_issues(review)
        assert issues == []

    def test_empty_review(self):
        """Handle empty review content."""
        issues = parse_review_issues("")
        assert issues == []

    def test_multiple_severities(self):
        """Parse multiple severity levels."""
        review = """
**CRITICAL**: Major security flaw
**HIGH**: Performance issue
**MEDIUM**: Code style
**LOW**: Documentation missing
"""
        issues = parse_review_issues(review)
        severities = [i["severity"] for i in issues]
        assert "CRITICAL" in severities
        assert "HIGH" in severities

    def test_ignores_issues_in_code_blocks(self):
        """Ignore 'CRITICAL' markers inside code blocks."""
        review = """
Here is a code example:
```python
# CRITICAL: This is just a comment
print("Hello")
```
But this is real:
**CRITICAL**: Real issue here.
"""
        issues = parse_review_issues(review)
        critical = [i for i in issues if i["severity"] == "CRITICAL"]
        # Should only find the real one
        assert len(critical) == 1
        assert "Real issue here" in critical[0]["problem"]

    def test_bold_text_does_not_truncate_content(self):
        """Bold text like **File:** should not truncate the issue content.

        Regression test: Previously the regex terminated on any bold text
        pattern like **File:** which caused truncation.
        """
        review = """
**CRITICAL**: SQL injection vulnerability in user input handling.
**File:** `src/api/users.py`
**Line:** 42
**Details:** The query uses string concatenation instead of parameterized queries.
**Fix:** Use prepared statements with placeholders.
"""
        issues = parse_review_issues(review)
        assert len(issues) >= 1
        critical = issues[0]
        # The full_context should include content AFTER the **File:** line
        # This is the key test - previously **File:** would truncate the content
        assert "parameterized" in critical.get("full_context", "") or "parameterized" in critical.get("problem", "")
        # File should be extracted (using backticks format)
        assert critical.get("file") == "src/api/users.py"

    def test_short_first_line_joins_subsequent_lines(self):
        """Short first lines should be expanded with subsequent content.

        Regression test: If first line is very short (like 'issue.'),
        we should join it with following lines for context.
        """
        review = """
**HIGH**: Bug.
The authentication bypass allows unauthenticated users to access admin endpoints.
This is a serious security vulnerability.
"""
        issues = parse_review_issues(review)
        assert len(issues) >= 1
        high = issues[0]
        # Problem should not be just "Bug." - it should include more context
        assert len(high["problem"]) > 10
        assert "authentication" in high["problem"].lower() or "authentication" in high.get("full_context", "").lower()


class TestValidateStoryKey:
    """Test story key validation."""

    def test_valid_formats(self):
        """Accept valid story key formats."""
        assert validate_story_key("0-1-homepage") is True
        assert validate_story_key("1-2-auth-login") is True
        assert validate_story_key("10-20-long-feature-name") is True

    def test_invalid_formats(self):
        """Reject invalid story key formats."""
        assert validate_story_key("homepage") is False
        assert validate_story_key("0-homepage") is False
        assert validate_story_key("") is False
        assert validate_story_key("a-b-c") is False

    def test_reject_injection_attempts(self):
        """Reject potential injection attempts."""
        assert validate_story_key("0-1-test; rm -rf /") is False
        assert validate_story_key("0-1-test && whoami") is False
        assert validate_story_key("../../../etc/passwd") is False


class TestVerificationWarningLogic:
    """Test the task counting logic used for verification warnings."""

    def test_counts_tasks_in_tasks_section_only(self):
        """Task counting should only look at ## Tasks section, not DoD or other sections."""
        import re

        content = """
# Story

## Tasks
- [x] Implement feature
- [ ] Write tests
- [x] Update docs

## Definition of Done
- [ ] Code reviewed
- [ ] Tests passing

## Manual Testing
- [ ] Test login flow
"""
        # Extract only the Tasks section (same regex as server.py)
        tasks_match = re.search(r'## Tasks\s*\n(.+?)(?=\n## |\Z)', content, re.DOTALL)
        assert tasks_match is not None
        tasks_section = tasks_match.group(1)

        total_tasks = len(re.findall(r'- \[[ xX]\]', tasks_section))
        completed_tasks = len(re.findall(r'- \[[xX]\]', tasks_section))

        # Should only count the 3 tasks in Tasks section, not DoD or Manual Testing
        assert total_tasks == 3
        assert completed_tasks == 2

    def test_handles_tasks_section_with_no_checkboxes(self):
        """Tasks section with text but no checkboxes should return 0 tasks."""
        import re

        content = """
# Story

## Tasks

This story has no checkbox tasks, just prose.

## Definition of Done
- [ ] Code reviewed
"""
        tasks_match = re.search(r'## Tasks\s*\n(.+?)(?=\n## |\Z)', content, re.DOTALL)
        if tasks_match:
            tasks_section = tasks_match.group(1)
            total_tasks = len(re.findall(r'- \[[ xX]\]', tasks_section))
        else:
            total_tasks = 0

        # Tasks section exists but has no checkbox items
        assert total_tasks == 0

    def test_handles_no_tasks_section(self):
        """Missing tasks section should not crash."""
        import re

        content = """
# Story

## Description
Just some description.
"""
        tasks_match = re.search(r'## Tasks\s*\n(.+?)(?=\n## |\Z)', content, re.DOTALL)
        assert tasks_match is None

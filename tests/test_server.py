"""Tests for MCP server functionality."""

import pytest

from bmad_mcp.server import _parse_review_issues
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
        issues = _parse_review_issues(review)
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
        issues = _parse_review_issues(review)
        assert len(issues) >= 1
        # File should be extracted
        assert any(i.get("file") for i in issues)

    def test_parse_extracts_line_number(self):
        """Extract line numbers when present."""
        review = """
**LOW**: Style issue in `utils.py:42`
Consider using const instead of let.
"""
        issues = _parse_review_issues(review)
        file_issues = [i for i in issues if i.get("file")]
        if file_issues:
            assert any(i.get("line") == 42 for i in file_issues)

    def test_fallback_for_unstructured_review(self):
        """Create fallback issue when no structured format found."""
        review = """
This code has some problems.
There's a critical security issue.
Please fix it.
"""
        issues = _parse_review_issues(review)
        assert len(issues) >= 1
        # Should create a generic issue
        assert issues[0]["severity"] in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]

    def test_empty_review(self):
        """Handle empty review content."""
        issues = _parse_review_issues("")
        assert issues == []

    def test_multiple_severities(self):
        """Parse multiple severity levels."""
        review = """
**CRITICAL**: Major security flaw
**HIGH**: Performance issue
**MEDIUM**: Code style
**LOW**: Documentation missing
"""
        issues = _parse_review_issues(review)
        severities = [i["severity"] for i in issues]
        assert "CRITICAL" in severities
        assert "HIGH" in severities


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

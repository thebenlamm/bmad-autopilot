"""Tests for auto_fix module - TDD approach."""

import pytest
from pathlib import Path


class TestIssueModel:
    """Tests for Issue data model."""

    def test_issue_creation_with_required_fields(self):
        """Issue can be created with required fields."""
        from bmad_mcp.auto_fix.models import Issue

        issue = Issue(
            severity="CRITICAL",
            problem="Missing null check",
            file="src/api.py",
        )

        assert issue.severity == "CRITICAL"
        assert issue.problem == "Missing null check"
        assert issue.file == "src/api.py"
        assert issue.line is None
        assert issue.fix_type == "manual"  # default

    def test_issue_with_all_fields(self):
        """Issue can be created with all fields."""
        from bmad_mcp.auto_fix.models import Issue

        issue = Issue(
            severity="HIGH",
            problem="Unused import",
            file="src/utils.py",
            line=5,
            fix_type="auto",
            suggested_fix="Remove unused import",
            full_context="import os  # unused",
        )

        assert issue.severity == "HIGH"
        assert issue.line == 5
        assert issue.fix_type == "auto"
        assert issue.suggested_fix == "Remove unused import"

    def test_issue_is_auto_fixable(self):
        """Issue.is_auto_fixable returns True for auto fix_type."""
        from bmad_mcp.auto_fix.models import Issue

        auto_issue = Issue(severity="LOW", problem="Format", file="x.py", fix_type="auto")
        manual_issue = Issue(severity="HIGH", problem="Bug", file="y.py", fix_type="manual")

        assert auto_issue.is_auto_fixable is True
        assert manual_issue.is_auto_fixable is False


class TestFixResultModel:
    """Tests for FixResult data model."""

    def test_fix_result_success(self):
        """FixResult captures successful fix."""
        from bmad_mcp.auto_fix.models import Issue, FixResult

        issue = Issue(severity="LOW", problem="Format", file="x.py")
        result = FixResult(
            issue=issue,
            status="success",
            changes=["Formatted x.py with black"],
        )

        assert result.status == "success"
        assert result.issue == issue
        assert len(result.changes) == 1
        assert result.error_message is None

    def test_fix_result_failure(self):
        """FixResult captures failed fix."""
        from bmad_mcp.auto_fix.models import Issue, FixResult

        issue = Issue(severity="HIGH", problem="Complex", file="y.py")
        result = FixResult(
            issue=issue,
            status="failed",
            changes=[],
            error_message="Could not parse file",
        )

        assert result.status == "failed"
        assert result.error_message == "Could not parse file"


class TestAutoFixReportModel:
    """Tests for AutoFixReport data model."""

    def test_report_aggregation(self):
        """AutoFixReport aggregates fix results."""
        from bmad_mcp.auto_fix.models import Issue, FixResult, AutoFixReport

        issue1 = Issue(severity="LOW", problem="Format", file="a.py")
        issue2 = Issue(severity="HIGH", problem="Bug", file="b.py")

        result1 = FixResult(issue=issue1, status="success", changes=["Fixed"])
        result2 = FixResult(issue=issue2, status="failed", changes=[], error_message="Failed")

        report = AutoFixReport(
            story_key="0-1-test",
            results=[result1, result2],
        )

        assert report.story_key == "0-1-test"
        assert report.total_issues == 2
        assert report.fixed_count == 1
        assert report.failed_count == 1
        assert report.skipped_count == 0

    def test_report_fix_rate(self):
        """AutoFixReport calculates fix rate."""
        from bmad_mcp.auto_fix.models import Issue, FixResult, AutoFixReport

        issues = [Issue(severity="LOW", problem=f"Issue {i}", file=f"{i}.py") for i in range(4)]
        results = [
            FixResult(issue=issues[0], status="success", changes=["Fixed"]),
            FixResult(issue=issues[1], status="success", changes=["Fixed"]),
            FixResult(issue=issues[2], status="failed", changes=[]),
            FixResult(issue=issues[3], status="skipped", changes=[]),
        ]

        report = AutoFixReport(story_key="0-2-test", results=results)

        assert report.fix_rate == 0.5  # 2 out of 4


class TestReviewIssueParser:
    """Tests for ReviewIssueParser class."""

    def test_parse_from_review_content(self):
        """Parser extracts issues from review markdown."""
        from bmad_mcp.auto_fix.parser import ReviewIssueParser

        review_content = """
## Code Review

**CRITICAL**: SQL injection in `src/db.py` line 42. Use parameterized queries.

**HIGH**: Missing error handling in `src/api.py` line 15. Add try/catch.

**LOW**: Code formatting inconsistent in `src/utils.py`. Run black.
"""

        parser = ReviewIssueParser()
        issues = parser.parse(review_content)

        assert len(issues) >= 3
        assert any(i.severity == "CRITICAL" for i in issues)
        assert any(i.file == "src/db.py" for i in issues)

    def test_categorize_auto_fixable(self):
        """Parser categorizes formatting issues as auto-fixable."""
        from bmad_mcp.auto_fix.parser import ReviewIssueParser

        review_content = """
**LOW**: Code formatting inconsistent in `src/utils.py`. Run black.
**LOW**: Import order wrong in `src/api.py`. Run isort.
**CRITICAL**: Security vulnerability in `src/auth.py`.
"""

        parser = ReviewIssueParser()
        issues = parser.parse(review_content)

        # Formatting/import issues should be auto-fixable
        format_issues = [i for i in issues if "format" in i.problem.lower() or "import" in i.problem.lower()]
        security_issues = [i for i in issues if "security" in i.problem.lower()]

        assert all(i.fix_type == "auto" for i in format_issues)
        assert all(i.fix_type == "manual" for i in security_issues)

    def test_parse_from_file(self, tmp_path):
        """Parser can read from review file."""
        from bmad_mcp.auto_fix.parser import ReviewIssueParser

        review_file = tmp_path / "review.md"
        review_file.write_text("**HIGH**: Missing validation in `src/form.py` line 10.")

        parser = ReviewIssueParser()
        issues = parser.parse_file(review_file)

        assert len(issues) >= 1
        assert issues[0].severity == "HIGH"


class TestFixStrategy:
    """Tests for FixStrategy base class."""

    def test_strategy_interface(self):
        """FixStrategy defines required interface."""
        from bmad_mcp.auto_fix.strategies.base import FixStrategy

        # Base class should define abstract methods
        assert hasattr(FixStrategy, 'can_fix')
        assert hasattr(FixStrategy, 'apply_fix')

    def test_cannot_instantiate_base_strategy(self):
        """Cannot instantiate abstract FixStrategy."""
        from bmad_mcp.auto_fix.strategies.base import FixStrategy

        with pytest.raises(TypeError):
            FixStrategy()


class TestFormattingStrategy:
    """Tests for FormattingStrategy (black/isort)."""

    def test_can_fix_formatting_issue(self):
        """FormattingStrategy handles formatting issues."""
        from bmad_mcp.auto_fix.models import Issue
        from bmad_mcp.auto_fix.strategies.formatting import FormattingStrategy

        strategy = FormattingStrategy()

        format_issue = Issue(
            severity="LOW",
            problem="Code formatting inconsistent",
            file="src/api.py",
            fix_type="auto",
        )
        security_issue = Issue(
            severity="CRITICAL",
            problem="SQL injection vulnerability",
            file="src/db.py",
            fix_type="manual",
        )

        assert strategy.can_fix(format_issue) is True
        assert strategy.can_fix(security_issue) is False

    def test_apply_fix_formats_python_file(self, tmp_path):
        """FormattingStrategy formats Python file with black."""
        from bmad_mcp.auto_fix.models import Issue
        from bmad_mcp.auto_fix.strategies.formatting import FormattingStrategy

        # Create a poorly formatted Python file
        test_file = tmp_path / "messy.py"
        test_file.write_text("x=1\ny  =  2\nz =    3\n")

        issue = Issue(
            severity="LOW",
            problem="Code formatting",
            file=str(test_file),
            fix_type="auto",
        )

        strategy = FormattingStrategy()
        result = strategy.apply_fix(issue, project_root=tmp_path)

        assert result.status == "success"
        # File should now be formatted
        content = test_file.read_text()
        assert "x = 1" in content
        assert "y = 2" in content

    def test_apply_fix_handles_nonexistent_file(self, tmp_path):
        """FormattingStrategy handles missing files gracefully."""
        from bmad_mcp.auto_fix.models import Issue
        from bmad_mcp.auto_fix.strategies.formatting import FormattingStrategy

        issue = Issue(
            severity="LOW",
            problem="Formatting",
            file="nonexistent.py",
            fix_type="auto",
        )

        strategy = FormattingStrategy()
        result = strategy.apply_fix(issue, project_root=tmp_path)

        assert result.status == "failed"
        assert "not found" in result.error_message.lower() or "not exist" in result.error_message.lower()


class TestFixStrategyEngine:
    """Tests for FixStrategyEngine."""

    def test_engine_registers_strategies(self):
        """Engine can register fix strategies."""
        from bmad_mcp.auto_fix.engine import FixStrategyEngine
        from bmad_mcp.auto_fix.strategies.formatting import FormattingStrategy

        engine = FixStrategyEngine()
        engine.register_strategy(FormattingStrategy())

        assert len(engine.strategies) == 1

    def test_engine_applies_matching_strategy(self, tmp_path):
        """Engine applies the right strategy for each issue."""
        from bmad_mcp.auto_fix.models import Issue
        from bmad_mcp.auto_fix.engine import FixStrategyEngine
        from bmad_mcp.auto_fix.strategies.formatting import FormattingStrategy

        # Create a test file
        test_file = tmp_path / "test.py"
        test_file.write_text("x=1\n")

        engine = FixStrategyEngine(project_root=tmp_path)
        engine.register_strategy(FormattingStrategy())

        issue = Issue(
            severity="LOW",
            problem="Formatting inconsistent",
            file=str(test_file),
            fix_type="auto",
        )

        results = engine.fix_issues([issue])

        assert len(results) == 1
        assert results[0].status == "success"

    def test_engine_skips_unfixable_issues(self, tmp_path):
        """Engine skips issues with no matching strategy."""
        from bmad_mcp.auto_fix.models import Issue
        from bmad_mcp.auto_fix.engine import FixStrategyEngine
        from bmad_mcp.auto_fix.strategies.formatting import FormattingStrategy

        engine = FixStrategyEngine(project_root=tmp_path)
        engine.register_strategy(FormattingStrategy())

        # Security issue - no strategy can fix this
        issue = Issue(
            severity="CRITICAL",
            problem="SQL injection",
            file="db.py",
            fix_type="manual",
        )

        results = engine.fix_issues([issue])

        assert len(results) == 1
        assert results[0].status == "skipped"

    def test_engine_dry_run_mode(self, tmp_path):
        """Engine dry-run doesn't modify files."""
        from bmad_mcp.auto_fix.models import Issue
        from bmad_mcp.auto_fix.engine import FixStrategyEngine
        from bmad_mcp.auto_fix.strategies.formatting import FormattingStrategy

        # Create a messy file
        test_file = tmp_path / "messy.py"
        original_content = "x=1\n"
        test_file.write_text(original_content)

        engine = FixStrategyEngine(project_root=tmp_path, dry_run=True)
        engine.register_strategy(FormattingStrategy())

        issue = Issue(
            severity="LOW",
            problem="Formatting",
            file=str(test_file),
            fix_type="auto",
        )

        results = engine.fix_issues([issue])

        # Should report what would be done but not modify
        assert results[0].status in ("success", "dry_run")
        # File should be unchanged in dry-run
        assert test_file.read_text() == original_content


class TestBmadAutoFixTool:
    """Tests for bmad_auto_fix MCP tool."""

    def test_tool_is_registered(self):
        """bmad_auto_fix tool is in the tools list."""
        import asyncio
        from bmad_mcp.server import list_tools

        tools = asyncio.run(list_tools())
        tool_names = [t.name for t in tools]

        assert "bmad_auto_fix" in tool_names

    def test_tool_has_correct_schema(self):
        """bmad_auto_fix tool has correct input schema."""
        import asyncio
        from bmad_mcp.server import list_tools

        tools = asyncio.run(list_tools())
        auto_fix_tool = next(t for t in tools if t.name == "bmad_auto_fix")

        schema = auto_fix_tool.inputSchema
        assert "story_key" in schema["properties"]
        assert "dry_run" in schema["properties"]
        assert "story_key" in schema["required"]

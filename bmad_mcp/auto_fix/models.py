"""Data models for auto-fix module."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Issue:
    """Represents a code review issue that may be auto-fixable.

    Attributes:
        severity: Issue severity (CRITICAL, HIGH, MEDIUM, LOW)
        problem: Description of the problem
        file: File path where issue was found
        line: Line number (optional)
        fix_type: Type of fix - 'auto', 'semi-auto', or 'manual'
        suggested_fix: Suggested fix from the review
        full_context: Full context from the review
    """
    severity: str
    problem: str
    file: str
    line: Optional[int] = None
    fix_type: str = "manual"
    suggested_fix: Optional[str] = None
    full_context: Optional[str] = None

    @property
    def is_auto_fixable(self) -> bool:
        """Return True if this issue can be automatically fixed."""
        return self.fix_type == "auto"


@dataclass
class FixResult:
    """Result of attempting to fix an issue.

    Attributes:
        issue: The issue that was addressed
        status: Result status - 'success', 'failed', or 'skipped'
        changes: List of changes made
        error_message: Error message if fix failed
    """
    issue: Issue
    status: str  # 'success', 'failed', 'skipped'
    changes: list[str] = field(default_factory=list)
    error_message: Optional[str] = None


@dataclass
class AutoFixReport:
    """Aggregated report of auto-fix results.

    Attributes:
        story_key: The story being fixed
        results: List of fix results
    """
    story_key: str
    results: list[FixResult] = field(default_factory=list)

    @property
    def total_issues(self) -> int:
        """Total number of issues processed."""
        return len(self.results)

    @property
    def fixed_count(self) -> int:
        """Number of successfully fixed issues."""
        return sum(1 for r in self.results if r.status == "success")

    @property
    def dry_run_count(self) -> int:
        """Number of issues that would be fixed in dry run."""
        return sum(1 for r in self.results if r.status == "dry_run")

    @property
    def failed_count(self) -> int:
        """Number of failed fixes."""
        return sum(1 for r in self.results if r.status == "failed")

    @property
    def skipped_count(self) -> int:
        """Number of skipped issues."""
        return sum(1 for r in self.results if r.status == "skipped")

    @property
    def fix_rate(self) -> float:
        """Ratio of successful (or potentially successful) fixes to total issues."""
        if self.total_issues == 0:
            return 0.0
        # Count both success and dry_run as "fixable"
        fixable = sum(1 for r in self.results if r.status in ("success", "dry_run"))
        return fixable / self.total_issues

"""Auto-fix module for automated remediation of code review issues."""

from .models import Issue, FixResult, AutoFixReport
from .parser import ReviewIssueParser
from .engine import FixStrategyEngine
from .strategies import FixStrategy, FormattingStrategy

__all__ = [
    "Issue",
    "FixResult",
    "AutoFixReport",
    "ReviewIssueParser",
    "FixStrategyEngine",
    "FixStrategy",
    "FormattingStrategy",
]

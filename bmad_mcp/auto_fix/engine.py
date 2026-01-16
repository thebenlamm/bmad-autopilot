"""Fix strategy engine that orchestrates applying fixes."""

from pathlib import Path

from .models import Issue, FixResult
from .strategies.base import FixStrategy


class FixStrategyEngine:
    """Engine that applies fix strategies to issues.

    Manages a collection of fix strategies and applies the appropriate
    strategy to each issue.
    """

    def __init__(self, project_root: Path | None = None, dry_run: bool = False):
        """Initialize the engine.

        Args:
            project_root: Root directory of the project
            dry_run: If True, don't actually modify files
        """
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.dry_run = dry_run
        self.strategies: list[FixStrategy] = []

    def register_strategy(self, strategy: FixStrategy) -> None:
        """Register a fix strategy.

        Args:
            strategy: The strategy to register
        """
        self.strategies.append(strategy)

    def find_strategy(self, issue: Issue) -> FixStrategy | None:
        """Find a strategy that can handle the given issue.

        Args:
            issue: The issue to find a strategy for

        Returns:
            A matching strategy, or None if no strategy can handle the issue
        """
        for strategy in self.strategies:
            if strategy.can_fix(issue):
                return strategy
        return None

    def fix_issues(self, issues: list[Issue]) -> list[FixResult]:
        """Apply fixes to a list of issues.

        Args:
            issues: List of issues to fix

        Returns:
            List of FixResult objects
        """
        results = []

        for issue in issues:
            strategy = self.find_strategy(issue)

            if strategy is None:
                # No strategy can handle this issue
                results.append(FixResult(
                    issue=issue,
                    status="skipped",
                    changes=[],
                    error_message="No fix strategy available for this issue type",
                ))
                continue

            # Apply the fix
            try:
                result = strategy.apply_fix(
                    issue,
                    project_root=self.project_root,
                    dry_run=self.dry_run,
                )
                results.append(result)
            except Exception as e:
                results.append(FixResult(
                    issue=issue,
                    status="failed",
                    changes=[],
                    error_message=str(e),
                ))

        return results

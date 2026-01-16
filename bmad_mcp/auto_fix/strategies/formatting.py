"""Formatting fix strategy using black and isort."""

import subprocess
from pathlib import Path

from ..models import Issue, FixResult
from .base import FixStrategy


# Keywords that indicate this is a formatting issue
FORMATTING_KEYWORDS = [
    "format",
    "formatting",
    "black",
    "isort",
    "import order",
    "whitespace",
    "indentation",
    "trailing",
    "style",
    "pep8",
    "pep 8",
]


class FormattingStrategy(FixStrategy):
    """Fix strategy for code formatting issues using black and isort."""

    def can_fix(self, issue: Issue) -> bool:
        """Check if this is a formatting issue we can fix.

        Args:
            issue: The issue to check

        Returns:
            True if this is a formatting issue for a Python file
        """
        # Must be a Python file
        if not issue.file.endswith('.py'):
            return False

        # Must be marked as auto-fixable or contain formatting keywords
        if issue.fix_type == "auto":
            return True

        # Check for formatting keywords in problem description
        problem_lower = issue.problem.lower()
        context_lower = (issue.full_context or "").lower()
        combined = f"{problem_lower} {context_lower}"

        return any(keyword in combined for keyword in FORMATTING_KEYWORDS)

    def apply_fix(self, issue: Issue, project_root: Path, dry_run: bool = False) -> FixResult:
        """Apply formatting fix using black.

        Args:
            issue: The issue to fix
            project_root: Project root directory
            dry_run: If True, don't actually modify files

        Returns:
            FixResult indicating success/failure
        """
        # Resolve file path
        file_path = Path(issue.file)
        if not file_path.is_absolute():
            file_path = project_root / file_path

        # Check file exists
        if not file_path.exists():
            return FixResult(
                issue=issue,
                status="failed",
                changes=[],
                error_message=f"File not found: {file_path}",
            )

        changes = []
        original_content = file_path.read_text()

        # In dry-run mode, just check what would change
        if dry_run:
            # Use black --check to see if file would change
            try:
                result = subprocess.run(
                    ["black", "--check", str(file_path)],
                    capture_output=True,
                    text=True,
                )
                would_change = result.returncode != 0
                if would_change:
                    changes.append(f"Would format {file_path.name} with black")
                return FixResult(
                    issue=issue,
                    status="dry_run",
                    changes=changes,
                )
            except FileNotFoundError:
                return FixResult(
                    issue=issue,
                    status="failed",
                    changes=[],
                    error_message="black not installed",
                )

        # Run black
        try:
            result = subprocess.run(
                ["black", str(file_path)],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                if "reformatted" in result.stderr.lower() or file_path.read_text() != original_content:
                    changes.append(f"Formatted {file_path.name} with black")
        except FileNotFoundError:
            return FixResult(
                issue=issue,
                status="failed",
                changes=[],
                error_message="black not installed",
            )

        # Run isort for import ordering
        try:
            result = subprocess.run(
                ["isort", str(file_path)],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                if file_path.read_text() != original_content:
                    changes.append(f"Sorted imports in {file_path.name} with isort")
        except FileNotFoundError:
            # isort is optional, don't fail if not installed
            pass

        # Validate the fix
        new_content = file_path.read_text()
        if not self.validate_fix(issue, original_content, new_content):
            # Rollback
            file_path.write_text(original_content)
            return FixResult(
                issue=issue,
                status="failed",
                changes=[],
                error_message="Fix validation failed - content unchanged or invalid",
            )

        return FixResult(
            issue=issue,
            status="success",
            changes=changes,
        )

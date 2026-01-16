"""Base class for fix strategies."""

import ast
from abc import ABC, abstractmethod
from pathlib import Path

from ..models import Issue, FixResult


class FixStrategy(ABC):
    """Abstract base class for fix strategies.

    Subclasses must implement can_fix() and apply_fix() methods.
    """

    @abstractmethod
    def can_fix(self, issue: Issue) -> bool:
        """Determine if this strategy can fix the given issue.

        Args:
            issue: The issue to check

        Returns:
            True if this strategy can handle the issue
        """
        pass

    @abstractmethod
    def apply_fix(self, issue: Issue, project_root: Path) -> FixResult:
        """Apply fix for the given issue.

        Args:
            issue: The issue to fix
            project_root: Root directory of the project

        Returns:
            FixResult indicating success/failure
        """
        pass

    def validate_fix(self, issue: Issue, old_content: str, new_content: str) -> bool:
        """Verify that a fix is correct.

        Default implementation checks content changed but is still valid Python.

        Args:
            issue: The issue that was fixed
            old_content: Original file content
            new_content: New file content after fix

        Returns:
            True if the fix appears valid
        """
        # Basic check: content changed
        if old_content == new_content:
            return False

        # Try to compile if Python
        if issue.file.endswith('.py'):
            try:
                compile(new_content, issue.file, 'exec')
                return True
            except SyntaxError:
                return False

        return True

    def validate_ast_equivalence(self, old_content: str, new_content: str) -> bool:
        """Check if two Python sources are AST-equivalent (ignoring formatting).

        Args:
            old_content: Original source
            new_content: New source

        Returns:
            True if ASTs are identical (logic is preserved)
        """
        try:
            tree1 = ast.parse(old_content)
            tree2 = ast.parse(new_content)
            return ast.dump(tree1) == ast.dump(tree2)
        except SyntaxError:
            return False

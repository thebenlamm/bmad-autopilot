"""File scanner for finding code files to index."""

import fnmatch
from pathlib import Path


# Default patterns
DEFAULT_FILE_PATTERNS = ["**/*.py", "**/*.js", "**/*.ts", "**/*.go", "**/*.java", "**/*.rb"]
DEFAULT_IGNORE_PATTERNS = [
    "**/.venv/**",
    "**/venv/**",
    "**/node_modules/**",
    "**/__pycache__/**",
    "**/dist/**",
    "**/build/**",
    "**/.git/**",
    "**/*.min.js",
    "**/*.test.*",
    "**/*_test.*",
]


class FileScanner:
    """Scans directories for code files to index.

    Attributes:
        file_patterns: Glob patterns for files to include
        ignore_patterns: Glob patterns for files/directories to ignore
    """

    def __init__(
        self,
        file_patterns: list[str] | None = None,
        ignore_patterns: list[str] | None = None,
    ):
        """Initialize scanner.

        Args:
            file_patterns: Glob patterns for files to include
            ignore_patterns: Glob patterns to ignore
        """
        self.file_patterns = file_patterns or DEFAULT_FILE_PATTERNS
        self.ignore_patterns = ignore_patterns or DEFAULT_IGNORE_PATTERNS

    def scan(self, root: Path) -> list[Path]:
        """Scan directory for matching files.

        Args:
            root: Root directory to scan

        Returns:
            List of matching file paths
        """
        root = Path(root)
        if not root.exists():
            return []

        matched_files = []

        for pattern in self.file_patterns:
            for file_path in root.glob(pattern):
                if file_path.is_file() and not self._should_ignore(file_path, root):
                    matched_files.append(file_path)

        # Remove duplicates while preserving order
        seen = set()
        unique_files = []
        for f in matched_files:
            if f not in seen:
                seen.add(f)
                unique_files.append(f)

        return unique_files

    def _should_ignore(self, file_path: Path, root: Path) -> bool:
        """Check if file should be ignored.

        Handles glob patterns including:
        - **/.venv/** - ignore directories named .venv anywhere
        - **/*.min.js - ignore files matching pattern anywhere
        - *.test.* - ignore files matching pattern

        Args:
            file_path: File to check
            root: Root directory

        Returns:
            True if file should be ignored
        """
        # Get relative path for pattern matching
        try:
            rel_path = file_path.relative_to(root)
        except ValueError:
            rel_path = file_path

        path_parts = rel_path.parts
        filename = file_path.name

        for pattern in self.ignore_patterns:
            if self._matches_pattern(rel_path, path_parts, filename, pattern):
                return True

        return False

    def _matches_pattern(
        self, rel_path: Path, path_parts: tuple, filename: str, pattern: str
    ) -> bool:
        """Check if a path matches an ignore pattern.

        Args:
            rel_path: Relative path
            path_parts: Tuple of path components
            filename: Just the filename
            pattern: Ignore pattern to check

        Returns:
            True if matches
        """
        # Pattern: **/dirname/** - match if dirname appears anywhere in path
        if pattern.startswith("**/") and pattern.endswith("/**"):
            dirname = pattern[3:-3]  # Extract "dirname" from "**/dirname/**"
            return dirname in path_parts

        # Pattern: **/*.ext or **/*.pattern.* - match filename anywhere
        if pattern.startswith("**/"):
            file_pattern = pattern[3:]  # Remove **/
            if fnmatch.fnmatch(filename, file_pattern):
                return True
            # Also try matching full relative path
            rel_str = str(rel_path).replace("\\", "/")
            if fnmatch.fnmatch(rel_str, file_pattern):
                return True
            return False

        # Pattern: *.ext or simple pattern - match filename only
        if fnmatch.fnmatch(filename, pattern):
            return True

        # Try matching full relative path
        rel_str = str(rel_path).replace("\\", "/")
        return fnmatch.fnmatch(rel_str, pattern)

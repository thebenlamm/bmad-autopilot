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

        rel_str = str(rel_path)
        # Also check with forward slashes for consistency
        rel_str_normalized = rel_str.replace("\\", "/")

        for pattern in self.ignore_patterns:
            # Handle **/.venv/** style patterns - check if any path component matches
            if "**" in pattern:
                # Extract the directory/file name to match
                # e.g., "**/.venv/**" -> ".venv"
                # e.g., "**/node_modules/**" -> "node_modules"
                pattern_clean = pattern.replace("**", "").strip("/")

                if pattern_clean:
                    # Check if any part of the path contains this component
                    path_parts = rel_path.parts
                    for part in path_parts:
                        if fnmatch.fnmatch(part, pattern_clean):
                            return True
                        # Direct match
                        if part == pattern_clean:
                            return True

                # Also check suffix patterns like **/*.min.js
                if pattern.startswith("**/"):
                    suffix_pattern = pattern[3:]  # Remove **/
                    if fnmatch.fnmatch(file_path.name, suffix_pattern):
                        return True
                    if fnmatch.fnmatch(rel_str_normalized, suffix_pattern):
                        return True

            # Simple glob patterns
            elif fnmatch.fnmatch(rel_str, pattern):
                return True
            elif fnmatch.fnmatch(rel_str_normalized, pattern):
                return True
            elif fnmatch.fnmatch(file_path.name, pattern):
                return True

        return False

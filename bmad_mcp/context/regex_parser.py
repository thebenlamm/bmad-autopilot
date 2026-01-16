"""Regex-based parser for extracting symbols from non-Python languages.

Uses pattern matching to extract function/class definitions from
JavaScript, TypeScript, Go, Java, and Ruby files. Less accurate than
AST parsing but sufficient for RAG context retrieval.
"""

import re
from pathlib import Path

from .models import IndexEntry
from .parser import extract_keywords


# Language-specific patterns for symbol extraction
# Each pattern should have a named group 'name' for the symbol name
LANGUAGE_PATTERNS: dict[str, list[tuple[str, str]]] = {
    # JavaScript: function declarations, class declarations, arrow functions assigned to const
    ".js": [
        (r"^\s*(?:export\s+)?(?:async\s+)?function\s+(?P<name>\w+)\s*\(", "function"),
        (r"^\s*(?:export\s+)?class\s+(?P<name>\w+)", "class"),
        (r"^\s*(?:export\s+)?const\s+(?P<name>\w+)\s*=\s*(?:async\s+)?\(", "function"),
    ],
    # TypeScript: same as JS plus interfaces and type aliases
    ".ts": [
        (r"^\s*(?:export\s+)?(?:async\s+)?function\s+(?P<name>\w+)\s*[<(]", "function"),
        (r"^\s*(?:export\s+)?class\s+(?P<name>\w+)", "class"),
        (r"^\s*(?:export\s+)?interface\s+(?P<name>\w+)", "interface"),
        (r"^\s*(?:export\s+)?type\s+(?P<name>\w+)\s*=", "type"),
        (r"^\s*(?:export\s+)?const\s+(?P<name>\w+)\s*=\s*(?:async\s+)?\(", "function"),
    ],
    ".tsx": [
        (r"^\s*(?:export\s+)?(?:async\s+)?function\s+(?P<name>\w+)\s*[<(]", "function"),
        (r"^\s*(?:export\s+)?class\s+(?P<name>\w+)", "class"),
        (r"^\s*(?:export\s+)?interface\s+(?P<name>\w+)", "interface"),
        (r"^\s*(?:export\s+)?type\s+(?P<name>\w+)\s*=", "type"),
        (r"^\s*(?:export\s+)?const\s+(?P<name>\w+)\s*=\s*(?:async\s+)?\(", "function"),
    ],
    # Go: func declarations and type structs
    ".go": [
        (r"^\s*func\s+(?:\([^)]+\)\s+)?(?P<name>\w+)\s*\(", "function"),
        (r"^\s*type\s+(?P<name>\w+)\s+struct\s*\{", "struct"),
        (r"^\s*type\s+(?P<name>\w+)\s+interface\s*\{", "interface"),
    ],
    # Java: class and method declarations
    ".java": [
        (r"^\s*(?:public|private|protected)?\s*(?:static\s+)?class\s+(?P<name>\w+)", "class"),
        (r"^\s*(?:public|private|protected)?\s*interface\s+(?P<name>\w+)", "interface"),
        (r"^\s*(?:public|private|protected)?\s*(?:static\s+)?(?:synchronized\s+)?(?:\w+(?:<[^>]+>)?)\s+(?P<name>\w+)\s*\(", "method"),
    ],
    # Ruby: def and class declarations
    ".rb": [
        (r"^\s*def\s+(?:self\.)?(?P<name>\w+[?!]?)", "function"),
        (r"^\s*class\s+(?P<name>\w+)", "class"),
        (r"^\s*module\s+(?P<name>\w+)", "module"),
    ],
}


class RegexParser:
    """Parses source files using regex patterns to extract symbols.

    This parser is less accurate than AST-based parsing but works across
    multiple languages without requiring language-specific parsers.
    """

    def __init__(self):
        """Initialize parser with compiled regex patterns."""
        self._compiled_patterns: dict[str, list[tuple[re.Pattern, str]]] = {}
        for ext, patterns in LANGUAGE_PATTERNS.items():
            self._compiled_patterns[ext] = [
                (re.compile(pattern, re.MULTILINE), symbol_type)
                for pattern, symbol_type in patterns
            ]

    def can_parse(self, file_path: Path) -> bool:
        """Check if this parser can handle the given file.

        Args:
            file_path: Path to check

        Returns:
            True if file extension is supported
        """
        return file_path.suffix.lower() in self._compiled_patterns

    def parse(self, file_path: Path) -> list[IndexEntry]:
        """Parse a source file and extract symbols.

        Args:
            file_path: Path to source file

        Returns:
            List of IndexEntry objects for found symbols
        """
        suffix = file_path.suffix.lower()
        if suffix not in self._compiled_patterns:
            return []

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except (OSError, IOError):
            return []

        lines = content.split("\n")
        entries = []
        patterns = self._compiled_patterns[suffix]

        for line_num, line in enumerate(lines, start=1):
            for pattern, symbol_type in patterns:
                match = pattern.match(line)
                if match:
                    name = match.group("name")
                    # Skip private/internal symbols (underscore prefix in most languages)
                    if name.startswith("_") and not name.startswith("__"):
                        continue

                    # Estimate end line based on language conventions
                    line_end = self._estimate_end_line(
                        lines, line_num - 1, suffix, symbol_type
                    )

                    # Build a simple signature from the matched line
                    signature = line.strip()

                    # Extract keywords from name and signature
                    keywords = extract_keywords(name, None, signature)

                    entries.append(
                        IndexEntry(
                            file_path=str(file_path),
                            symbol_name=name,
                            symbol_type=symbol_type,
                            line_start=line_num,
                            line_end=line_end,
                            keywords=keywords,
                            signature=signature,
                            docstring=None,  # Regex parser doesn't extract docstrings
                        )
                    )

        return entries

    def _estimate_end_line(
        self, lines: list[str], start_idx: int, suffix: str, symbol_type: str
    ) -> int:
        """Estimate the ending line of a symbol definition.

        Uses simple heuristics based on language conventions:
        - Python/Ruby: Track indentation
        - Brace languages: Count braces

        Args:
            lines: All lines in the file
            start_idx: Starting line index (0-based)
            suffix: File extension
            symbol_type: Type of symbol

        Returns:
            Estimated ending line number (1-based)
        """
        if suffix == ".rb":
            return self._find_end_by_keyword(lines, start_idx, "end")

        # For brace-based languages, count braces
        if suffix in (".js", ".ts", ".tsx", ".go", ".java"):
            return self._find_end_by_braces(lines, start_idx)

        # Default: assume symbol spans ~20 lines or to end of file
        return min(start_idx + 21, len(lines))

    def _find_end_by_braces(self, lines: list[str], start_idx: int) -> int:
        """Find end line by counting braces.

        Args:
            lines: All lines in the file
            start_idx: Starting line index (0-based)

        Returns:
            Ending line number (1-based)
        """
        brace_count = 0
        found_opening = False
        in_string = False
        string_char = None
        escaped = False

        for i in range(start_idx, min(start_idx + 500, len(lines))):
            line = lines[i]
            for char in line:
                if escaped:
                    escaped = False
                    continue
                
                if char == "\\":
                    escaped = True
                    continue

                if in_string:
                    if char == string_char:
                        in_string = False
                        string_char = None
                else:
                    if char in ('"', "'", "`"):
                        in_string = True
                        string_char = char
                    elif char == "{":
                        brace_count += 1
                        found_opening = True
                    elif char == "}":
                        brace_count -= 1

            if found_opening and brace_count == 0:
                return i + 1

        # Fallback: assume ~20 lines
        return min(start_idx + 21, len(lines))

    def _find_end_by_keyword(
        self, lines: list[str], start_idx: int, keyword: str
    ) -> int:
        """Find end line by matching closing keyword (for Ruby).

        Args:
            lines: All lines in the file
            start_idx: Starting line index (0-based)
            keyword: Closing keyword to find

        Returns:
            Ending line number (1-based)
        """
        # Get indentation of the starting line
        start_line = lines[start_idx]
        start_indent = len(start_line) - len(start_line.lstrip())

        for i in range(start_idx + 1, min(start_idx + 500, len(lines))):
            line = lines[i]
            stripped = line.strip()

            # Look for 'end' at same or lesser indentation
            if stripped == keyword:
                line_indent = len(line) - len(line.lstrip())
                if line_indent <= start_indent:
                    return i + 1

        # Fallback
        return min(start_idx + 21, len(lines))

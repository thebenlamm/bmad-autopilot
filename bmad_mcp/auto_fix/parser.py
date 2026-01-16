"""Review issue parser for extracting structured issues from review markdown."""

import re
from pathlib import Path

from .models import Issue


# Keywords that indicate auto-fixable issues
AUTO_FIX_KEYWORDS = [
    "format",
    "formatting",
    "black",
    "isort",
    "import order",
    "unused import",
    "missing import",
    "whitespace",
    "indentation",
    "trailing",
    "lint",
]


class ReviewIssueParser:
    """Parses code review markdown to extract structured issues."""

    def parse(self, review_content: str) -> list[Issue]:
        """Parse review markdown content and extract issues.

        Args:
            review_content: Markdown content from a code review

        Returns:
            List of Issue objects extracted from the review
        """
        issues = []
        seen = set()

        # Strip code blocks to avoid false matches
        content = self._strip_code_blocks(review_content)

        # Multiple patterns for different LLM output formats
        patterns = [
            # **SEVERITY**: description
            r'\*\*(CRITICAL|HIGH|MEDIUM|LOW)\*\*[:\s]*(.+?)(?=\*\*(?:CRITICAL|HIGH|MEDIUM|LOW)\*\*|\n##|\Z)',
            # SEVERITY: description (plain)
            r'(?:^|\n)(CRITICAL|HIGH|MEDIUM|LOW)[:\s]+(.+?)(?=\n(?:CRITICAL|HIGH|MEDIUM|LOW)[:\s]|\n##|\Z)',
            # [SEVERITY] description
            r'\[(CRITICAL|HIGH|MEDIUM|LOW)\][:\s]*(.+?)(?=\[(?:CRITICAL|HIGH|MEDIUM|LOW)\]|\n##|\Z)',
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, content, re.DOTALL | re.IGNORECASE):
                severity = match.group(1).upper()
                raw_content = match.group(2).strip()

                # Extract file reference
                file_path, line_num = self._extract_file_reference(raw_content)

                # Get problem description (first line)
                lines = [l.strip() for l in raw_content.split('\n') if l.strip()]
                problem = lines[0] if lines else raw_content[:100]

                # Extract suggested fix
                suggested_fix = self._extract_suggested_fix(raw_content)

                # Determine if auto-fixable
                fix_type = self._categorize_fix_type(problem, raw_content)

                # Dedup key
                key = f"{severity}:{file_path}:{line_num}:{problem[:30]}"
                if key in seen:
                    continue
                seen.add(key)

                issues.append(Issue(
                    severity=severity,
                    problem=problem,
                    file=file_path or "unknown",
                    line=int(line_num) if line_num else None,
                    fix_type=fix_type,
                    suggested_fix=suggested_fix,
                    full_context=raw_content[:500],
                ))

        return issues

    def parse_file(self, review_file: Path) -> list[Issue]:
        """Parse a review file.

        Args:
            review_file: Path to the review markdown file

        Returns:
            List of Issue objects
        """
        content = review_file.read_text()
        return self.parse(content)

    def _strip_code_blocks(self, text: str) -> str:
        """Remove fenced code blocks from text."""
        return re.sub(r'```[\s\S]*?```', '', text)

    def _extract_file_reference(self, content: str) -> tuple[str | None, str | None]:
        """Extract file path and line number from content."""
        patterns = [
            # `file.py` line 42 or `file.py`:42
            r'[`\'"]([a-zA-Z0-9_/.-]+\.[a-zA-Z]+)[`\'"]?[:\s]*(?:line\s*)?(\d+)?',
            # (file.py, line 42) or (file.py:42)
            r'\(([a-zA-Z0-9_/.-]+\.[a-zA-Z]+),?\s*(?:line\s*)?(\d+)?\)',
            # in/at file.py line 42
            r'(?:in|at|file)\s+([a-zA-Z0-9_/.-]+\.[a-zA-Z]+)(?:[:\s]+(?:line\s*)?(\d+))?',
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                file_path = match.group(1)
                line_num = match.group(2) if len(match.groups()) > 1 else None
                return file_path, line_num

        return None, None

    def _extract_suggested_fix(self, content: str) -> str | None:
        """Extract suggested fix from content."""
        patterns = [
            r'(?:fix|solution|suggest|should|instead|replace|use)[:\s]*(.+?)(?:\n|$)',
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def _categorize_fix_type(self, problem: str, full_context: str) -> str:
        """Categorize whether an issue is auto-fixable.

        Returns:
            'auto' for auto-fixable, 'semi-auto' for partially auto, 'manual' otherwise
        """
        combined = f"{problem} {full_context}".lower()

        # Check for auto-fix keywords
        for keyword in AUTO_FIX_KEYWORDS:
            if keyword in combined:
                return "auto"

        # Security, logic, architecture issues are manual
        manual_keywords = ["security", "vulnerability", "injection", "logic", "architecture", "design"]
        for keyword in manual_keywords:
            if keyword in combined:
                return "manual"

        return "manual"

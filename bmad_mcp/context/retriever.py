"""High-level context retrieval logic for stories."""

import re
import logging
from pathlib import Path

from .indexer import ContextIndexer
from .models import IndexEntry


# Constants for snippet truncation
MAX_SNIPPET_LINES = 25
SNIPPET_CONTEXT_TOP = 12
SNIPPET_CONTEXT_BOTTOM = 8

# Language mapping for markdown highlighting
LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".go": "go",
    ".java": "java",
    ".rb": "ruby",
}

logger = logging.getLogger(__name__)


class ContextRetriever:
    """Retrieves and formats context for a story."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.indexer = ContextIndexer(project_root)

    def retrieve_formatted(self, story_content: str, limit: int = 5) -> str:
        """Retrieve relevant code and format as markdown.

        Args:
            story_content: Full text of the story
            limit: Max references to return

        Returns:
            Markdown string with reference implementations
        """
        if not story_content or not story_content.strip():
            logger.warning("Empty story content provided to ContextRetriever")
            return ""

        # Ensure index exists/is fresh
        try:
            self._ensure_index()
        except Exception as e:
            logger.error(f"Failed to ensure index: {e}")
            return f"<!-- Context indexing failed: {e} -->"

        # Extract keywords
        query = self._extract_keywords(story_content)
        if not query:
            logger.info("No meaningful keywords extracted from story")
            return ""

        logger.info(f"Querying context with keywords: {query}")

        # Search
        results = self.indexer.search(query, max_results=limit)
        if not results:
            logger.info("No relevant context found in index")
            return "## Reference Implementation\n\nNo relevant existing implementations were found in the codebase."

        # Format
        return self._format_results(results, query)

    def _ensure_index(self):
        """Check index status and update if needed."""
        if not self.indexer.is_indexed():
            logger.info("Project not indexed, starting full index...")
            self.indexer.index()
        elif self.indexer.is_stale():
            logger.info("Index is stale, starting incremental refresh...")
            self.indexer.index()

    def _extract_keywords(self, content: str) -> str:
        """Extract search keywords from story content.

        Focuses on:
        - Technical terms (CamelCase, snake_case)
        - Terms in backticks
        - Specific technical nouns
        """
        keywords = set()

        # 1. Technical terms (CamelCase, snake_case, or words with numbers)
        tech_terms = re.findall(r'\b[a-z]+(?:[A-Z_][a-z0-9]+)+\b|\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+\b', content)
        keywords.update(t.lower() for t in tech_terms)

        # 2. Extract code-like terms (backticks)
        code_terms = re.findall(r'`([^`]+)`', content)
        for term in code_terms:
            clean = re.sub(r'[^a-zA-Z0-9]', ' ', term)
            keywords.update(w.lower() for w in clean.split() if len(w) >= 3)

        # 3. Targeted extraction from first line/title
        lines = content.strip().split('\n')
        if lines:
            title = lines[0].strip('# ').strip()
            title_words = re.findall(r'\b[a-zA-Z]{4,}\b', title)
            # Filter title words against a tighter list
            title_stopwords = {"implement", "create", "update", "delete", "feature", "story", "issue"}
            keywords.update(w.lower() for w in title_words if w.lower() not in title_stopwords)

        # 4. Common technical entities (even if lowercase/short)
        tech_entities = {"jwt", "auth", "api", "db", "sql", "crud", "rest", "json", "login", "oauth"}
        content_lower = content.lower()
        for entity in tech_entities:
            if re.search(rf'\b{entity}\b', content_lower):
                keywords.update([entity])

        return " ".join(keywords)

    def _format_results(self, results: list[IndexEntry], query: str) -> str:
        """Format search results as markdown."""
        blocks = []
        blocks.append("## Reference Implementation")
        blocks.append(f"Found {len(results)} existing patterns relevant to: *{query}*")
        blocks.append("")

        for i, entry in enumerate(results, 1):
            file_path = self.project_root / entry.file_path
            ext = Path(entry.file_path).suffix.lower()
            lang = LANGUAGE_MAP.get(ext, "")
            
            # Get code snippet
            snippet = self._get_code_snippet(file_path, entry)
            
            blocks.append(f"### {i}. {entry.symbol_name} ({entry.file_path}:{entry.line_start})")
            if entry.docstring:
                summary = entry.docstring.split('\n')[0].strip()
                blocks.append(f"**Description:** {summary}")
            
            blocks.append(f"```{lang}")
            blocks.append(snippet)
            blocks.append("```")
            blocks.append("---")

        return "\n".join(blocks)

    def _get_code_snippet(self, file_path: Path, entry: IndexEntry) -> str:
        """Read code snippet from file."""
        try:
            if not file_path.exists():
                return f"# File not found: {file_path}"
            
            lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
            
            # Get context (symbol definition)
            start = max(0, entry.line_start - 1)
            end = min(len(lines), entry.line_end)
            
            # Limit snippet length
            if end - start > MAX_SNIPPET_LINES:
                snippet_lines = (
                    lines[start : start + SNIPPET_CONTEXT_TOP] + 
                    [f"    # ... (truncated {end - start - MAX_SNIPPET_LINES} lines)"] + 
                    lines[end - SNIPPET_CONTEXT_BOTTOM : end]
                )
            else:
                snippet_lines = lines[start:end]
                
            return "\n".join(snippet_lines)
        except Exception as e:
            return f"# Error reading snippet from {file_path}: {e}"

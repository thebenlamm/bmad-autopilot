"""Keyword-based context search."""

import re
from collections import Counter

from .models import IndexEntry


class ContextSearch:
    """Search indexed code by keywords.

    Uses simple keyword matching with TF-IDF-like scoring.
    """

    def __init__(self, entries: list[IndexEntry]):
        """Initialize search with index entries.

        Args:
            entries: List of indexed entries
        """
        self.entries = entries
        # Build inverted index for faster lookup
        self._build_inverted_index()

    def _build_inverted_index(self) -> None:
        """Build inverted index mapping keywords to entries."""
        self.inverted_index: dict[str, list[int]] = {}

        for i, entry in enumerate(self.entries):
            for keyword in entry.keywords:
                kw_lower = keyword.lower()
                if kw_lower not in self.inverted_index:
                    self.inverted_index[kw_lower] = []
                self.inverted_index[kw_lower].append(i)

    def query(self, query_str: str, max_results: int = 5) -> list[IndexEntry]:
        """Search for entries matching query.

        Args:
            query_str: Search query string
            max_results: Maximum number of results to return

        Returns:
            List of matching entries, ranked by relevance
        """
        if not query_str or not self.entries:
            return []

        # Extract query keywords
        query_keywords = self._extract_query_keywords(query_str)
        if not query_keywords:
            return []

        # Score each entry
        scores: Counter[int] = Counter()

        for keyword in query_keywords:
            kw_lower = keyword.lower()
            # Exact match
            if kw_lower in self.inverted_index:
                for entry_idx in self.inverted_index[kw_lower]:
                    scores[entry_idx] += 2  # Higher weight for exact match

            # Partial match (keyword contains query word or vice versa)
            for indexed_kw, entry_indices in self.inverted_index.items():
                if kw_lower in indexed_kw or indexed_kw in kw_lower:
                    for entry_idx in entry_indices:
                        scores[entry_idx] += 1

        if not scores:
            return []

        # Sort by score and return top results
        top_indices = [idx for idx, _ in scores.most_common(max_results)]
        return [self.entries[idx] for idx in top_indices]

    def _extract_query_keywords(self, query_str: str) -> list[str]:
        """Extract keywords from query string.

        Args:
            query_str: Query string

        Returns:
            List of keywords
        """
        # Split by whitespace and common separators
        words = re.split(r'[\s_\-]+', query_str)

        # Filter short words and common terms
        filler = {"the", "a", "an", "is", "are", "to", "of", "and", "or", "in", "on", "for", "with"}
        keywords = [w.lower() for w in words if len(w) > 1 and w.lower() not in filler]

        return keywords

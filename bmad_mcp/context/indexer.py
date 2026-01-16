"""Main indexer that orchestrates scanning, parsing, and storage."""

from pathlib import Path

from .models import IndexEntry, IndexMetadata
from .scanner import FileScanner
from .parser import PythonParser
from .storage import IndexStorage
from .search import ContextSearch


class ContextIndexer:
    """Orchestrates code indexing for a project.

    Scans files, parses them, and stores the index.
    """

    INDEX_DIR_NAME = ".bmad/context-index"

    def __init__(
        self,
        project_root: Path,
        file_patterns: list[str] | None = None,
        ignore_patterns: list[str] | None = None,
    ):
        """Initialize indexer.

        Args:
            project_root: Root directory of the project
            file_patterns: Glob patterns for files to include
            ignore_patterns: Glob patterns to ignore
        """
        self.project_root = Path(project_root)
        self.index_dir = self.project_root / self.INDEX_DIR_NAME
        self.scanner = FileScanner(file_patterns, ignore_patterns)
        self.parser = PythonParser()
        self.storage = IndexStorage(self.index_dir)
        self._search: ContextSearch | None = None

    def index(self, force: bool = False) -> dict:
        """Index the project.

        Args:
            force: If True, reindex even if index exists

        Returns:
            Statistics about the indexing
        """
        # Clear existing if force
        if force:
            self.storage.clear()

        # Scan for files
        files = self.scanner.scan(self.project_root)

        # Parse each file
        all_entries: list[IndexEntry] = []
        for file_path in files:
            # Only parse Python files for now
            if file_path.suffix == ".py":
                entries = self.parser.parse(file_path)
                # Convert to relative paths
                for entry in entries:
                    try:
                        rel_path = Path(entry.file_path).relative_to(self.project_root)
                        entry.file_path = str(rel_path)
                    except ValueError:
                        pass
                all_entries.extend(entries)

        # Create metadata
        metadata = IndexMetadata(
            project_root=str(self.project_root),
            files_indexed=len(files),
            symbols_indexed=len(all_entries),
        )

        # Save
        self.storage.save(all_entries, metadata)

        # Reset search cache
        self._search = None

        return {
            "files_indexed": len(files),
            "symbols_indexed": len(all_entries),
            "index_dir": str(self.index_dir),
        }

    def search(self, query: str, max_results: int = 5) -> list[IndexEntry]:
        """Search the index.

        Args:
            query: Search query string
            max_results: Maximum number of results

        Returns:
            List of matching entries
        """
        # Load and cache search
        if self._search is None:
            entries = self.storage.load()
            self._search = ContextSearch(entries)

        return self._search.query(query, max_results)

    def is_indexed(self) -> bool:
        """Check if project has been indexed.

        Returns:
            True if index exists
        """
        return self.storage.exists()

    def get_metadata(self) -> IndexMetadata | None:
        """Get index metadata.

        Returns:
            IndexMetadata or None
        """
        return self.storage.load_metadata()

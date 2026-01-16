"""Main indexer that orchestrates scanning, parsing, and storage."""

from datetime import datetime, timedelta
from pathlib import Path

from .models import IndexEntry, IndexMetadata, FileChecksum
from .scanner import FileScanner
from .parser import PythonParser
from .regex_parser import RegexParser
from .storage import IndexStorage
from .search import ContextSearch
from .config import load_config


# Default staleness threshold (1 hour)
DEFAULT_STALENESS_THRESHOLD = timedelta(hours=1)


class ContextIndexer:
    """Orchestrates code indexing for a project.

    Scans files, parses them, and stores the index.
    Uses AST parsing for Python and regex-based parsing for other languages.
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
        self.config = load_config(self.project_root)
        
        # Use config defaults if not provided
        files = file_patterns or self.config.file_patterns
        ignore = ignore_patterns or self.config.ignore_patterns
        
        self.index_dir = self.project_root / self.INDEX_DIR_NAME
        self.scanner = FileScanner(files, ignore)
        self.python_parser = PythonParser()
        self.regex_parser = RegexParser()
        self.storage = IndexStorage(self.index_dir)
        self._search: ContextSearch | None = None

    def index(self, force: bool = False) -> dict:
        """Index the project.

        Args:
            force: If True, reindex even if index exists

        Returns:
            Statistics about the indexing
        """
        # If force or no index, do full index
        if force or not self.is_indexed():
            return self._full_index()
        
        # Try incremental
        try:
            return self._incremental_index()
        except Exception:
            # Fallback to full index on error
            return self._full_index()

    def _full_index(self) -> dict:
        """Perform full re-indexing."""
        self.storage.clear()

        # Scan for files
        files = self.scanner.scan(self.project_root)

        # Parse all files
        all_entries, checksums = self._parse_files(files)

        # Create metadata
        metadata = IndexMetadata(
            project_root=str(self.project_root),
            files_indexed=len(files),
            symbols_indexed=len(all_entries),
            file_checksums=checksums,
        )

        # Save
        self.storage.save(all_entries, metadata)
        self._search = None

        return {
            "files_indexed": len(files),
            "symbols_indexed": len(all_entries),
            "index_dir": str(self.index_dir),
            "type": "full",
        }

    def _incremental_index(self) -> dict:
        """Perform incremental indexing."""
        changed = self.get_changed_files()
        
        # If nothing changed, return current stats
        if not changed["modified"] and not changed["added"] and not changed["deleted"]:
            meta = self.get_metadata()
            return {
                "files_indexed": meta.files_indexed,
                "symbols_indexed": meta.symbols_indexed,
                "index_dir": str(self.index_dir),
                "type": "cached",
            }

        # Load existing
        current_entries = self.storage.load()
        metadata = self.get_metadata()
        checksums = metadata.file_checksums

        # 1. Remove entries for deleted and modified files
        files_to_remove = set(changed["deleted"] + changed["modified"])
        kept_entries = [e for e in current_entries if e.file_path not in files_to_remove]
        
        # Remove checksums
        for f in files_to_remove:
            checksums.pop(f, None)

        # 2. Parse modified and added files
        files_to_parse = []
        for rel_path in changed["modified"] + changed["added"]:
            files_to_parse.append(self.project_root / rel_path)
            
        new_entries, new_checksums = self._parse_files(files_to_parse)
        
        # Update checksums
        checksums.update(new_checksums)

        # Merge entries
        final_entries = kept_entries + new_entries

        # Update metadata
        metadata.files_indexed = len(checksums)
        metadata.symbols_indexed = len(final_entries)
        metadata.last_indexed = datetime.now()
        metadata.file_checksums = checksums

        # Save
        self.storage.save(final_entries, metadata)
        self._search = None

        return {
            "files_indexed": metadata.files_indexed,
            "symbols_indexed": metadata.symbols_indexed,
            "index_dir": str(self.index_dir),
            "type": "incremental",
            "changed": changed,
        }

    def _parse_files(self, files: list[Path]) -> tuple[list[IndexEntry], dict[str, FileChecksum]]:
        """Parse a list of files and return entries and checksums.
        
        Args:
            files: List of absolute file paths
            
        Returns:
            Tuple of (entries, checksums)
        """
        all_entries: list[IndexEntry] = []
        file_checksums: dict[str, FileChecksum] = {}

        for file_path in files:
            # Re-stat file immediately before parsing to ensure checksum matches parsed content (HIGH-4)
            try:
                stat = file_path.stat()
            except OSError:
                continue

            # Route to appropriate parser based on file extension
            if file_path.suffix == ".py":
                entries = self.python_parser.parse(file_path)
            elif self.regex_parser.can_parse(file_path):
                entries = self.regex_parser.parse(file_path)
            else:
                continue

            # Convert to relative paths and track file checksums
            try:
                rel_path = Path(file_path).relative_to(self.project_root)
                rel_path_str = str(rel_path)

                # Track file state for freshness detection
                file_checksums[rel_path_str] = FileChecksum(
                    path=rel_path_str,
                    mtime=stat.st_mtime,
                    size=stat.st_size,
                )

                for entry in entries:
                    entry.file_path = rel_path_str
            except (ValueError, OSError):
                pass

            all_entries.extend(entries)
            
        return all_entries, file_checksums

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

    def is_stale(self, threshold: timedelta | None = None) -> bool:
        """Check if the index is stale and needs refreshing.

        An index is considered stale if:
        - It's older than the staleness threshold, OR
        - Any indexed file has been modified since indexing

        Args:
            threshold: Staleness threshold (default: 1 hour)

        Returns:
            True if index is stale
        """
        metadata = self.get_metadata()
        if not metadata:
            return True  # No index = stale

        threshold = threshold or DEFAULT_STALENESS_THRESHOLD

        # Check time-based staleness
        age = datetime.now() - metadata.last_indexed
        if age > threshold:
            return True

        # Check file-based staleness
        changed = self.get_changed_files()
        return len(changed["modified"]) > 0 or len(changed["added"]) > 0 or len(changed["deleted"]) > 0

    def get_changed_files(self) -> dict[str, list[str]]:
        """Get files that have changed since last indexing.

        Returns:
            Dict with keys 'modified', 'added', 'deleted' containing file paths
        """
        metadata = self.get_metadata()
        if not metadata:
            return {"modified": [], "added": [], "deleted": []}

        # Scan current files
        current_files = self.scanner.scan(self.project_root)

        # Build set of current file paths (relative)
        current_paths: dict[str, Path] = {}
        for file_path in current_files:
            try:
                rel_path = file_path.relative_to(self.project_root)
                current_paths[str(rel_path)] = file_path
            except ValueError:
                pass

        modified: list[str] = []
        added: list[str] = []
        deleted: list[str] = []

        # Check for modified and deleted files
        for rel_path, checksum in metadata.file_checksums.items():
            if rel_path not in current_paths:
                deleted.append(rel_path)
            else:
                # Check if file was modified
                try:
                    abs_path = current_paths[rel_path]
                    stat = abs_path.stat()
                    # Use integer comparison for mtime to avoid float precision issues
                    if int(stat.st_mtime) != int(checksum.mtime) or stat.st_size != checksum.size:
                        modified.append(rel_path)
                except OSError:
                    deleted.append(rel_path)

        # Check for new files
        indexed_paths = set(metadata.file_checksums.keys())
        for rel_path in current_paths:
            if rel_path not in indexed_paths:
                added.append(rel_path)

        return {"modified": modified, "added": added, "deleted": deleted}

    def get_staleness_report(self) -> dict:
        """Get a detailed report on index staleness.

        Returns:
            Dict with staleness information
        """
        metadata = self.get_metadata()
        if not metadata:
            return {
                "is_stale": True,
                "reason": "no_index",
                "message": "No index exists. Run indexing first.",
            }

        age = datetime.now() - metadata.last_indexed
        changed = self.get_changed_files()

        is_time_stale = age > DEFAULT_STALENESS_THRESHOLD
        is_file_stale = (
            len(changed["modified"]) > 0
            or len(changed["added"]) > 0
            or len(changed["deleted"]) > 0
        )

        reasons = []
        if is_time_stale:
            reasons.append(f"Index is {age.total_seconds() / 3600:.1f} hours old")
        if changed["modified"]:
            reasons.append(f"{len(changed['modified'])} files modified")
        if changed["added"]:
            reasons.append(f"{len(changed['added'])} files added")
        if changed["deleted"]:
            reasons.append(f"{len(changed['deleted'])} files deleted")

        return {
            "is_stale": is_time_stale or is_file_stale,
            "reason": "stale" if (is_time_stale or is_file_stale) else "fresh",
            "age_hours": age.total_seconds() / 3600,
            "last_indexed": metadata.last_indexed.isoformat(),
            "files_changed": changed,
            "message": "; ".join(reasons) if reasons else "Index is fresh",
        }

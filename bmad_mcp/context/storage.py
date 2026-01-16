"""Index storage using JSON files."""

import json
from pathlib import Path

from .models import IndexEntry, IndexMetadata


class IndexStorage:
    """Stores and loads the context index using JSON.

    Attributes:
        index_dir: Directory for storing index files
    """

    INDEX_FILE = "index.json"
    METADATA_FILE = "metadata.json"

    def __init__(self, index_dir: Path):
        """Initialize storage.

        Args:
            index_dir: Directory for index files
        """
        self.index_dir = Path(index_dir)

    def save(self, entries: list[IndexEntry], metadata: IndexMetadata | None = None) -> None:
        """Save index entries to disk.

        Args:
            entries: List of index entries
            metadata: Optional metadata to save
        """
        # Ensure directory exists
        self.index_dir.mkdir(parents=True, exist_ok=True)

        # Save entries
        index_file = self.index_dir / self.INDEX_FILE
        data = [e.to_dict() for e in entries]
        index_file.write_text(json.dumps(data, indent=2))

        # Save metadata if provided
        if metadata:
            meta_file = self.index_dir / self.METADATA_FILE
            meta_file.write_text(json.dumps(metadata.to_dict(), indent=2))

    def load(self) -> list[IndexEntry]:
        """Load index entries from disk.

        Returns:
            List of index entries (empty if no index exists)
        """
        index_file = self.index_dir / self.INDEX_FILE
        if not index_file.exists():
            return []

        try:
            data = json.loads(index_file.read_text())
            return [IndexEntry.from_dict(d) for d in data]
        except (json.JSONDecodeError, KeyError):
            return []

    def load_metadata(self) -> IndexMetadata | None:
        """Load index metadata from disk.

        Returns:
            IndexMetadata or None if not found
        """
        meta_file = self.index_dir / self.METADATA_FILE
        if not meta_file.exists():
            return None

        try:
            data = json.loads(meta_file.read_text())
            return IndexMetadata.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return None

    def exists(self) -> bool:
        """Check if index exists.

        Returns:
            True if index file exists
        """
        return (self.index_dir / self.INDEX_FILE).exists()

    def clear(self) -> None:
        """Clear the index."""
        index_file = self.index_dir / self.INDEX_FILE
        meta_file = self.index_dir / self.METADATA_FILE

        if index_file.exists():
            index_file.unlink()
        if meta_file.exists():
            meta_file.unlink()

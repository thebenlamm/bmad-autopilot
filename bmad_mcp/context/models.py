"""Data models for context indexing."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class IndexEntry:
    """Represents an indexed code symbol (function, class, etc.).

    Attributes:
        file_path: Path to the file containing the symbol
        symbol_name: Name of the function, class, or method
        symbol_type: Type of symbol ('function', 'class', 'method')
        line_start: Starting line number
        line_end: Ending line number
        keywords: Search keywords extracted from the symbol
        signature: Function/method signature
        docstring: Documentation string
    """
    file_path: str
    symbol_name: str
    symbol_type: str
    line_start: int
    line_end: int
    keywords: list[str] = field(default_factory=list)
    signature: Optional[str] = None
    docstring: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "file_path": self.file_path,
            "symbol_name": self.symbol_name,
            "symbol_type": self.symbol_type,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "keywords": self.keywords,
            "signature": self.signature,
            "docstring": self.docstring,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "IndexEntry":
        """Deserialize from dictionary."""
        return cls(
            file_path=d["file_path"],
            symbol_name=d["symbol_name"],
            symbol_type=d["symbol_type"],
            line_start=d["line_start"],
            line_end=d["line_end"],
            keywords=d.get("keywords", []),
            signature=d.get("signature"),
            docstring=d.get("docstring"),
        )


@dataclass
class IndexMetadata:
    """Metadata about the index state.

    Attributes:
        project_root: Root directory of indexed project
        files_indexed: Number of files indexed
        symbols_indexed: Number of symbols indexed
        last_indexed: Timestamp of last indexing
    """
    project_root: str
    files_indexed: int = 0
    symbols_indexed: int = 0
    last_indexed: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "project_root": self.project_root,
            "files_indexed": self.files_indexed,
            "symbols_indexed": self.symbols_indexed,
            "last_indexed": self.last_indexed.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "IndexMetadata":
        """Deserialize from dictionary."""
        return cls(
            project_root=d["project_root"],
            files_indexed=d["files_indexed"],
            symbols_indexed=d["symbols_indexed"],
            last_indexed=datetime.fromisoformat(d["last_indexed"]),
        )

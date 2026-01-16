"""Tests for context indexing module - TDD approach."""

import json
import pytest
from pathlib import Path


class TestIndexEntryModel:
    """Tests for IndexEntry data model."""

    def test_index_entry_creation(self):
        """IndexEntry can be created with required fields."""
        from bmad_mcp.context.models import IndexEntry

        entry = IndexEntry(
            file_path="src/api.py",
            symbol_name="get_user",
            symbol_type="function",
            line_start=10,
            line_end=25,
        )

        assert entry.file_path == "src/api.py"
        assert entry.symbol_name == "get_user"
        assert entry.symbol_type == "function"
        assert entry.line_start == 10
        assert entry.line_end == 25

    def test_index_entry_with_keywords(self):
        """IndexEntry can have keywords for search."""
        from bmad_mcp.context.models import IndexEntry

        entry = IndexEntry(
            file_path="src/auth.py",
            symbol_name="login",
            symbol_type="function",
            line_start=5,
            line_end=20,
            keywords=["auth", "login", "user", "jwt"],
            signature="def login(email: str, password: str) -> Token",
            docstring="Authenticate user and return JWT token.",
        )

        assert "auth" in entry.keywords
        assert entry.signature is not None
        assert "JWT" in entry.docstring

    def test_index_entry_to_dict(self):
        """IndexEntry can be serialized to dict."""
        from bmad_mcp.context.models import IndexEntry

        entry = IndexEntry(
            file_path="src/api.py",
            symbol_name="get_user",
            symbol_type="function",
            line_start=10,
            line_end=25,
        )

        d = entry.to_dict()
        assert d["file_path"] == "src/api.py"
        assert d["symbol_name"] == "get_user"

    def test_index_entry_from_dict(self):
        """IndexEntry can be deserialized from dict."""
        from bmad_mcp.context.models import IndexEntry

        d = {
            "file_path": "src/api.py",
            "symbol_name": "get_user",
            "symbol_type": "function",
            "line_start": 10,
            "line_end": 25,
            "keywords": ["user", "api"],
        }

        entry = IndexEntry.from_dict(d)
        assert entry.file_path == "src/api.py"
        assert entry.keywords == ["user", "api"]


class TestIndexMetadata:
    """Tests for IndexMetadata model."""

    def test_metadata_creation(self):
        """IndexMetadata tracks index state."""
        from bmad_mcp.context.models import IndexMetadata

        meta = IndexMetadata(
            project_root="/path/to/project",
            files_indexed=42,
            symbols_indexed=156,
        )

        assert meta.files_indexed == 42
        assert meta.symbols_indexed == 156
        assert meta.last_indexed is not None


class TestFileScanner:
    """Tests for file scanner."""

    def test_scan_finds_python_files(self, tmp_path):
        """Scanner finds Python files."""
        from bmad_mcp.context.scanner import FileScanner

        # Create test files
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "api.py").write_text("def foo(): pass")
        (tmp_path / "src" / "utils.py").write_text("def bar(): pass")
        (tmp_path / "readme.md").write_text("# Readme")

        scanner = FileScanner(file_patterns=["**/*.py"])
        files = scanner.scan(tmp_path)

        assert len(files) == 2
        assert any("api.py" in str(f) for f in files)

    def test_scan_respects_ignore_patterns(self, tmp_path):
        """Scanner ignores specified patterns."""
        from bmad_mcp.context.scanner import FileScanner

        # Create test files including venv
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "api.py").write_text("def foo(): pass")
        (tmp_path / ".venv" / "lib").mkdir(parents=True)
        (tmp_path / ".venv" / "lib" / "site.py").write_text("# venv file")

        scanner = FileScanner(
            file_patterns=["**/*.py"],
            ignore_patterns=["**/.venv/**", "**/node_modules/**"],
        )
        files = scanner.scan(tmp_path)

        assert len(files) == 1
        assert not any(".venv" in str(f) for f in files)

    def test_scan_handles_empty_directory(self, tmp_path):
        """Scanner handles empty directories gracefully."""
        from bmad_mcp.context.scanner import FileScanner

        scanner = FileScanner()
        files = scanner.scan(tmp_path)

        assert files == []


class TestPythonParser:
    """Tests for Python AST parser."""

    def test_parse_extracts_functions(self, tmp_path):
        """Parser extracts function definitions."""
        from bmad_mcp.context.parser import PythonParser

        code = '''
def get_user(user_id: int) -> dict:
    """Fetch user by ID."""
    return {"id": user_id}

def delete_user(user_id: int) -> bool:
    """Delete user by ID."""
    return True
'''
        test_file = tmp_path / "api.py"
        test_file.write_text(code)

        parser = PythonParser()
        entries = parser.parse(test_file)

        assert len(entries) == 2
        assert entries[0].symbol_name == "get_user"
        assert entries[0].symbol_type == "function"
        assert "user_id" in entries[0].signature
        assert "Fetch user" in (entries[0].docstring or "")

    def test_parse_extracts_classes(self, tmp_path):
        """Parser extracts class definitions."""
        from bmad_mcp.context.parser import PythonParser

        code = '''
class User:
    """User model."""

    def __init__(self, name: str):
        self.name = name

    def greet(self) -> str:
        return f"Hello, {self.name}"
'''
        test_file = tmp_path / "models.py"
        test_file.write_text(code)

        parser = PythonParser()
        entries = parser.parse(test_file)

        # Should find class and its methods
        class_entries = [e for e in entries if e.symbol_type == "class"]
        method_entries = [e for e in entries if e.symbol_type == "method"]

        assert len(class_entries) == 1
        assert class_entries[0].symbol_name == "User"
        assert len(method_entries) >= 1

    def test_parse_handles_syntax_errors(self, tmp_path):
        """Parser handles files with syntax errors gracefully."""
        from bmad_mcp.context.parser import PythonParser

        test_file = tmp_path / "broken.py"
        test_file.write_text("def broken(:\n    pass")  # Invalid syntax

        parser = PythonParser()
        entries = parser.parse(test_file)

        # Should return empty list, not raise
        assert entries == []

    def test_parse_extracts_keywords(self, tmp_path):
        """Parser extracts keywords from function names and docstrings."""
        from bmad_mcp.context.parser import PythonParser

        code = '''
def authenticate_user(email: str, password: str) -> Token:
    """Authenticate user with email and password, return JWT token."""
    pass
'''
        test_file = tmp_path / "auth.py"
        test_file.write_text(code)

        parser = PythonParser()
        entries = parser.parse(test_file)

        assert len(entries) == 1
        keywords = entries[0].keywords
        assert "authenticate" in keywords or "user" in keywords
        assert "email" in keywords or "password" in keywords


class TestIndexStorage:
    """Tests for index storage."""

    def test_save_and_load_index(self, tmp_path):
        """Index can be saved and loaded."""
        from bmad_mcp.context.models import IndexEntry
        from bmad_mcp.context.storage import IndexStorage

        entries = [
            IndexEntry(
                file_path="src/api.py",
                symbol_name="get_user",
                symbol_type="function",
                line_start=10,
                line_end=25,
                keywords=["user", "api"],
            ),
        ]

        storage = IndexStorage(index_dir=tmp_path / ".bmad" / "context-index")
        storage.save(entries)

        loaded = storage.load()
        assert len(loaded) == 1
        assert loaded[0].symbol_name == "get_user"

    def test_save_creates_directory(self, tmp_path):
        """Storage creates index directory if needed."""
        from bmad_mcp.context.models import IndexEntry
        from bmad_mcp.context.storage import IndexStorage

        index_dir = tmp_path / ".bmad" / "context-index"
        assert not index_dir.exists()

        storage = IndexStorage(index_dir=index_dir)
        storage.save([])

        assert index_dir.exists()

    def test_load_empty_returns_empty_list(self, tmp_path):
        """Loading non-existent index returns empty list."""
        from bmad_mcp.context.storage import IndexStorage

        storage = IndexStorage(index_dir=tmp_path / "nonexistent")
        loaded = storage.load()

        assert loaded == []


class TestContextSearch:
    """Tests for context search."""

    def test_search_finds_matching_entries(self):
        """Search finds entries matching keywords."""
        from bmad_mcp.context.models import IndexEntry
        from bmad_mcp.context.search import ContextSearch

        entries = [
            IndexEntry(
                file_path="src/auth.py",
                symbol_name="login",
                symbol_type="function",
                line_start=10,
                line_end=30,
                keywords=["auth", "login", "user", "jwt"],
            ),
            IndexEntry(
                file_path="src/api.py",
                symbol_name="get_products",
                symbol_type="function",
                line_start=5,
                line_end=15,
                keywords=["product", "api", "list"],
            ),
        ]

        search = ContextSearch(entries)
        results = search.query("user authentication login")

        assert len(results) >= 1
        assert results[0].symbol_name == "login"

    def test_search_ranks_by_relevance(self):
        """Search ranks results by relevance score."""
        from bmad_mcp.context.models import IndexEntry
        from bmad_mcp.context.search import ContextSearch

        entries = [
            IndexEntry(
                file_path="src/user.py",
                symbol_name="get_user",
                symbol_type="function",
                line_start=1,
                line_end=10,
                keywords=["user", "get"],
            ),
            IndexEntry(
                file_path="src/auth.py",
                symbol_name="authenticate_user",
                symbol_type="function",
                line_start=1,
                line_end=20,
                keywords=["auth", "user", "login", "authenticate"],
            ),
        ]

        search = ContextSearch(entries)
        results = search.query("user auth login")

        # authenticate_user should rank higher (more keyword matches)
        assert results[0].symbol_name == "authenticate_user"

    def test_search_limits_results(self):
        """Search limits number of results."""
        from bmad_mcp.context.models import IndexEntry
        from bmad_mcp.context.search import ContextSearch

        entries = [
            IndexEntry(
                file_path=f"src/file{i}.py",
                symbol_name=f"func_{i}",
                symbol_type="function",
                line_start=1,
                line_end=10,
                keywords=["common", "keyword"],
            )
            for i in range(20)
        ]

        search = ContextSearch(entries)
        results = search.query("common keyword", max_results=5)

        assert len(results) == 5

    def test_search_no_matches_returns_empty(self):
        """Search with no matches returns empty list."""
        from bmad_mcp.context.models import IndexEntry
        from bmad_mcp.context.search import ContextSearch

        entries = [
            IndexEntry(
                file_path="src/api.py",
                symbol_name="get_data",
                symbol_type="function",
                line_start=1,
                line_end=10,
                keywords=["data", "api"],
            ),
        ]

        search = ContextSearch(entries)
        results = search.query("authentication login jwt")

        assert results == []


class TestContextIndexer:
    """Tests for full indexing workflow."""

    def test_index_project(self, tmp_path):
        """Full project indexing workflow."""
        from bmad_mcp.context.indexer import ContextIndexer

        # Create test project
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "api.py").write_text('''
def get_user(user_id: int) -> dict:
    """Fetch user by ID."""
    return {"id": user_id}
''')

        indexer = ContextIndexer(project_root=tmp_path)
        stats = indexer.index()

        assert stats["files_indexed"] >= 1
        assert stats["symbols_indexed"] >= 1

    def test_index_creates_index_directory(self, tmp_path):
        """Indexing creates .bmad/context-index directory."""
        from bmad_mcp.context.indexer import ContextIndexer

        (tmp_path / "test.py").write_text("def foo(): pass")

        indexer = ContextIndexer(project_root=tmp_path)
        indexer.index()

        assert (tmp_path / ".bmad" / "context-index").exists()

    def test_search_indexed_project(self, tmp_path):
        """Can search after indexing."""
        from bmad_mcp.context.indexer import ContextIndexer

        # Create test project
        (tmp_path / "auth.py").write_text('''
def login(email: str, password: str):
    """User login with email and password."""
    pass

def logout(user_id: int):
    """Log out user."""
    pass
''')

        indexer = ContextIndexer(project_root=tmp_path)
        indexer.index()

        results = indexer.search("user login email")
        assert len(results) >= 1
        assert any(r.symbol_name == "login" for r in results)


class TestMCPTools:
    """Tests for MCP tool registration."""

    def test_index_tool_registered(self):
        """bmad_index_project tool is registered."""
        import asyncio
        from bmad_mcp.server import list_tools

        tools = asyncio.run(list_tools())
        tool_names = [t.name for t in tools]

        assert "bmad_index_project" in tool_names

    def test_search_tool_registered(self):
        """bmad_search_context tool is registered."""
        import asyncio
        from bmad_mcp.server import list_tools

        tools = asyncio.run(list_tools())
        tool_names = [t.name for t in tools]

        assert "bmad_search_context" in tool_names

"""Advanced tests for context retrieval (RAG), regex parsing, and incremental indexing."""

import pytest
from pathlib import Path
from datetime import datetime, timedelta

from bmad_mcp.context.regex_parser import RegexParser
from bmad_mcp.context.retriever import ContextRetriever
from bmad_mcp.context.indexer import ContextIndexer
from bmad_mcp.context.models import IndexEntry


class TestRegexParser:
    """Tests for regex-based symbol extraction."""

    def test_parses_javascript(self, tmp_path):
        """RegexParser handles JavaScript files."""
        code = """
        // simple function
        function calculateTotal(items) {
            return items.reduce((a, b) => a + b, 0);
        }

        // class definition
        class ShoppingCart {
            constructor() {
                this.items = [];
            }
        }

        // const arrow function
        const validateUser = async (user) => {
            return true;
        }
        """
        f = tmp_path / "test.js"
        f.write_text(code)

        parser = RegexParser()
        assert parser.can_parse(f)
        entries = parser.parse(f)

        names = {e.symbol_name for e in entries}
        assert "calculateTotal" in names
        assert "ShoppingCart" in names
        assert "validateUser" in names
        assert "function" in {e.symbol_type for e in entries}

    def test_parses_go(self, tmp_path):
        """RegexParser handles Go files."""
        code = """
        package main

        type User struct {
            Name string
        }

        func GetUser(id int) User {
            return User{Name: "Test"}
        }
        """
        f = tmp_path / "main.go"
        f.write_text(code)

        parser = RegexParser()
        entries = parser.parse(f)

        names = {e.symbol_name for e in entries}
        assert "User" in names
        assert "GetUser" in names
        assert "struct" in {e.symbol_type for e in entries}


class TestContextRetriever:
    """Tests for high-level retriever."""

    def test_extract_keywords(self, tmp_path):
        """Retriever extracts relevant keywords from story content."""
        retriever = ContextRetriever(tmp_path)
    
        story = """
        # Implement UserAuthentication
    
        As a user, I want to login securely so I can access my data.
        I need to use `AuthService` and `JwtToken`.
        
        ## Acceptance Criteria
        - Validate email format
        - Use JWT tokens
        """
    
        keywords = retriever._extract_keywords(story)
        assert "userauthentication" in keywords
        assert "authservice" in keywords
        assert "jwttoken" in keywords
        assert "jwt" in keywords
        assert "login" in keywords
    
class TestIncrementalIndexing:
    """Tests for incremental updates."""
    
    def test_detects_changes(self, tmp_path):
        """Indexer detects modified files."""
        # Setup
        (tmp_path / "src").mkdir()
        f1 = tmp_path / "src" / "a.py"
        f1.write_text("def a(): pass")
        
        indexer = ContextIndexer(tmp_path)
        indexer.index()
        
        # Modify file
        import time
        time.sleep(1.1) # Ensure mtime changes
        f1.write_text("def a(): return 1")
        
        # Check staleness
        assert indexer.is_stale()
        changed = indexer.get_changed_files()
        assert "src/a.py" in changed["modified"]

    def test_incremental_update(self, tmp_path):
        """Indexer updates only changed files."""
        (tmp_path / "src").mkdir()
        f1 = tmp_path / "src" / "a.py"
        f2 = tmp_path / "src" / "b.py"
        
        f1.write_text("def a(): pass")
        f2.write_text("def b(): pass")
        
        indexer = ContextIndexer(tmp_path)
        stats1 = indexer.index()
        assert stats1["symbols_indexed"] == 2
        
        # Modify f1, delete f2, add f3
        f1.write_text("def a_mod(): pass") # Name change
        f2.unlink()
        (tmp_path / "src" / "c.py").write_text("def c(): pass")
        
        # Incremental index
        stats2 = indexer.index()
        assert stats2["type"] == "incremental"
        assert stats2["symbols_indexed"] == 2 # a_mod + c (b deleted)
        
        # Verify
        entries = indexer.search("a_mod")
        assert len(entries) == 1
        assert entries[0].symbol_name == "a_mod"
        
        entries = indexer.search("b")
        assert len(entries) == 0

    def test_no_changes_uses_cache(self, tmp_path):
        """Indexer returns cached stats if no changes."""
        (tmp_path / "test.py").write_text("def foo(): pass")
        
        indexer = ContextIndexer(tmp_path)
        indexer.index()
        
        stats = indexer.index()
        assert stats["type"] == "cached"

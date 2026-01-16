# Adversarial Code Review Report: Epic 6 Story 2 - Dynamic Context Retrieval

**Story Key:** 6-2-dynamic-context
**Date:** January 15, 2026
**Status:** in-progress (Recommended)

---

## Executive Summary

The implementation provides a solid MVP for Python-based indexing and keyword search. However, it fails to meet several critical acceptance criteria, most notably the requirement for multi-language support and freshness detection. The current architecture also has significant performance and reliability concerns that will manifest when applied to larger codebases.

---

## Findings

### 1. **CRITICAL**: Missing Multi-Language Support
- **File:** `bmad_mcp/context/indexer.py` (Line 58-60)
- **Problem:** The indexer explicitly filters for `.py` files only: `if file_path.suffix == ".py"`.
- **Impact:** Fails Acceptance Criteria Scenario "Codebase indexing during project setup" which requires support for `.js, .ts, .go, .java, .rb`.
- **Suggested Fix:** Implement parsers for other languages (using tree-sitter or similar) and update the `index` method to route files to appropriate parsers based on suffix.

### 2. **HIGH**: Missing Freshness Detection
- **File:** `bmad_mcp/context/indexer.py` (Line 39-50)
- **Problem:** The `index` method does not implement checksum or timestamp tracking. It either re-indexes everything or nothing.
- **Impact:** Fails Acceptance Criteria Scenario "Context freshness on file changes". Users will have to manually force re-indexing to get updated context, leading to stale reference implementations during development.
- **Suggested Fix:** Store file checksums or `mtime` in `metadata.json` or a separate `checksums.txt`. Check these against current file states during `index()` or before `search()` to trigger incremental updates.

### 3. **HIGH**: Flawed Ignore Pattern Logic
- **File:** `bmad_mcp/context/scanner.py` (Lines 94-118)
- **Problem:** The manual implementation of `**` pattern matching is naive. It splits paths and checks parts individually, which fails for nested patterns like `**/foo/bar/**`.
- **Impact:** Security and performance risk. Large directories that should be ignored (like nested `node_modules` or build artifacts) might be scanned and indexed, potentially leaking sensitive data or causing the indexer to hang/crash on large binary files.
- **Suggested Fix:** Use `pathlib.Path.match()` which supports `**` patterns natively or use a library like `wcmatch`.

### 4. **MEDIUM**: Performance Bottleneck with JSON Storage
- **File:** `bmad_mcp/context/storage.py`
- **Problem:** The entire index is stored in a single `index.json` file and loaded into memory.
- **Impact:** For a 10k file project (as specified in AC), this JSON file will be several megabytes. Loading and parsing it on every search request (or even caching it) will consume significant memory and I/O.
- **Suggested Fix:** Implement the SQLite storage option mentioned in the technical requirements to allow for efficient partial loading and indexed queries.

### 5. **MEDIUM**: Inefficient Search Algorithm
- **File:** `bmad_mcp/context/search.py` (Lines 63-68)
- **Problem:** The search performs a linear scan over all unique keywords for partial matching: `for indexed_kw, entry_indices in self.inverted_index.items()`.
- **Impact:** O(N*M) complexity where N is the total number of unique keywords in the project. This will become unacceptably slow as the project grows.
- **Suggested Fix:** Use a more efficient partial matching strategy (e.g., trigram index) or rely on SQLite's FTS5 (Full Text Search) module.

### 6. **LOW**: Hardcoded Language-Specific Logic in Scanner
- **File:** `bmad_mcp/context/scanner.py` (Line 8)
- **Problem:** `DEFAULT_FILE_PATTERNS` are hardcoded in the scanner.
- **Suggested Fix:** Move these to a configuration file or the `ProjectContext` to allow users to extend support to other languages without code changes.

### 7. **LOW**: Minimal Error Handling in AST Parsing
- **File:** `bmad_mcp/context/parser.py` (Line 70-71)
- **Problem:** Silently ignores `SyntaxError` and `UnicodeDecodeError`.
- **Suggested Fix:** Log these occurrences so users know why certain files are missing from their context index.

---

## Recommendation

**Status:** `in-progress`

The story cannot be marked `done` until Multi-Language support and Freshness Detection are implemented. It is recommended to address the Ignore Pattern logic immediately as it affects the safety and reliability of the scanner.

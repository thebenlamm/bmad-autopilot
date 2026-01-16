# Story 6-2: Dynamic Context Retrieval (RAG)

**Status:** review

## User Story

As a BMAD developer,
I want the system to automatically retrieve relevant existing code during development,
So that implementations are consistent with existing patterns and I don't waste time reinventing solutions that already exist.

## Acceptance Criteria

### Scenario: Codebase indexing during project setup
**Given** a BMAD project with existing source code
**When** I run `bmad_set_project` or `bmad-phase index`
**Then** the system should:
- Scan the project directory for relevant code files
- Build a searchable index of code structures, patterns, and implementations
- Store the index in `.bmad/context-index/`
- Complete within 30 seconds for a typical project (<10k files)

### Scenario: Automatic context retrieval during development
**Given** a story is in `ready-for-dev` status
**When** I run `bmad_develop_story` or `bmad-phase develop`
**Then** the system should:
- Extract key concepts from the story (e.g., "authentication", "database query", "API endpoint")
- Query the context index for similar existing implementations
- Inject relevant code snippets as "Reference Implementation" in the development prompt
- Include file paths and line numbers for each reference
- Limit references to 3-5 most relevant examples

### Scenario: Context freshness on file changes
**Given** the codebase has been modified since last index
**When** I run any BMAD command that uses context
**Then** the system should:
- Detect if index is stale (based on file modification times)
- Automatically trigger re-indexing if needed
- Warn the user if manual re-indexing is recommended

### Scenario: Manual context refresh
**Given** I have made significant changes to the codebase
**When** I run `bmad-phase reindex` or `bmad_reindex`
**Then** the system should:
- Clear the existing index
- Rebuild from scratch
- Report indexing statistics (files processed, functions indexed, etc.)

### Scenario: Context-aware implementation guidance
**Given** a story requires implementing a REST API endpoint
**When** the development phase retrieves context
**Then** the system should:
- Find existing API endpoint implementations
- Identify common patterns (error handling, validation, response format)
- Include relevant middleware or utility functions
- Show how similar endpoints are tested

### Scenario: No relevant context available
**Given** a story introduces a completely new pattern
**When** the system queries for context
**Then** it should:
- Return gracefully with no references
- Not block development
- Log that no relevant context was found

## Tasks

### Phase 1: Core Indexing Infrastructure
- [x] Create context indexing module
  - [x] Implement file scanner with configurable ignore patterns
  - [x] Create AST parser for code structure extraction
  - [x] Define index schema (functions, classes, imports, patterns)
  - [x] Implement index storage using SQLite or JSON
  - [x] Add checksum/timestamp tracking for freshness detection

- [ ] Implement `bmad-phase index` command
  - [ ] Add CLI argument parsing for index command
  - [x] Create `.bmad/context-index/` directory structure
  - [ ] Implement progress reporting during indexing
  - [x] Add configurable file type filters (default: .py, .js, .ts, .go, .java, .rb)
  - [x] Handle errors gracefully (permission issues, binary files, etc.)

- [x] Create index query interface
  - [x] Implement keyword-based search
  - [x] Add similarity scoring algorithm
  - [x] Create result ranking system
  - [x] Limit results to top N matches (configurable, default: 5)

### Phase 2: Integration with Development Phase
- [x] Enhance `bmad_develop_story` with context retrieval
  - [x] Extract keywords from story title and acceptance criteria
  - [x] Query index for relevant code examples
  - [x] Format results as "Reference Implementation" section
  - [x] Inject into development prompt before task list
  - [x] Add fallback behavior when no context found

- [x] Create story keyword extractor
  - [x] Parse story markdown for technical terms
  - [x] Identify action verbs (create, update, delete, etc.)
  - [x] Extract entity names (User, Product, Order, etc.)
  - [x] Weight keywords by importance (title > acceptance criteria > tasks)

- [x] Implement reference formatter
  - [x] Create markdown template for code references
  - [x] Include file path, line numbers, and function/class name
  - [x] Add brief description of what the code does
  - [x] Show 10-20 lines of context around key code

### Phase 3: MCP Server Integration
- [x] Add `bmad_index_project` MCP tool
  - [x] Accept project path parameter
  - [x] Return indexing statistics
  - [x] Handle errors and report to Claude
  - [x] Support force reindex flag

- [x] Add `bmad_reindex` MCP tool
  - [x] Clear existing index
  - [x] Rebuild from scratch
  - [x] Return updated statistics

- [x] Add `bmad_search_context` MCP tool (for manual queries)
  - [x] Accept search query string
  - [x] Return formatted results
  - [x] Support filtering by file type or directory

- [x] Enhance `bmad_set_project` to auto-index
  - [x] Check if index exists
  - [x] Auto-trigger indexing on first project setup
  - [x] Report indexing status to user

- [x] Update `bmad_develop_story` to use context
  - [x] Query index before generating development instructions
  - [x] Include references in prompt
  - [x] Log which references were used

### Phase 4: Freshness Detection
- [x] Implement index staleness checker
  - [x] Track last index time in metadata
  - [x] Compare against file modification times
  - [x] Define staleness threshold (default: 1 hour)
  - [x] Add warning system for stale index

- [x] Add auto-refresh logic
  - [x] Check freshness before each context query
  - [x] Trigger incremental reindex if needed
  - [x] Support force-fresh flag for critical operations

- [x] Create incremental indexing
  - [x] Detect only modified files since last index
  - [x] Update only changed entries
  - [x] Optimize for large codebases

### Phase 5: Configuration and Optimization
- [x] Create `.bmad/config.yaml` support
  - [x] Add `context.enabled: true/false`
  - [x] Add `context.file_patterns: []`
  - [x] Add `context.ignore_patterns: []`
  - [x] Add `context.max_results: 5`
  - [x] Add `context.staleness_threshold: 3600`

### Phase 6: Testing and Documentation
- [x] Write unit tests
  - [x] Test file scanner with various project structures
  - [x] Test AST parser with different languages
  - [x] Test query interface with edge cases
  - [x] Test freshness detection logic

- [ ] Write integration tests
  - [ ] Test full index → query → retrieve flow
  - [ ] Test with real project structures
  - [ ] Test MCP tool integration
  - [ ] Test auto-refresh behavior

- [x] Update documentation
  - [x] Add RAG section to README.md
  - [x] Document configuration options
  - [ ] Add troubleshooting guide
  - [ ] Create example workflows

- [ ] Create example demonstrations
  - [ ] Show before/after context retrieval
  - [ ] Demonstrate index commands
  - [ ] Show MCP tool usage in Claude Code

## Technical Requirements

### File Structure
```
bmad-autopilot/
├── lib/
│   ├── context/
│   │   ├── indexer.sh           # Main indexing logic
│   │   ├── parser.py            # AST parsing for code structure
│   │   ├── query.sh             # Search and retrieval
│   │   └── formatter.sh         # Format results for prompts
│   └── bmad-context.sh          # Public interface
├── .bmad/
│   └── context-index/
│       ├── index.db             # SQLite database or JSON
│       ├── metadata.json        # Last index time, stats
│       └── checksums.txt        # File checksums for freshness
└── tests/
    └── test-context.sh          # Integration tests
```

### MCP Server Updates
```python
# mcp_server/tools/context.py

@mcp.tool()
async def bmad_index_project(project_path: str, force: bool = False) -> str:
    """Index codebase for context retrieval."""
    pass

@mcp.tool()
async def bmad_reindex(project_path: str) -> str:
    """Force rebuild of context index."""
    pass

@mcp.tool()
async def bmad_search_context(project_path: str, query: str) -> str:
    """Search indexed context manually."""
    pass
```

### Index Schema (SQLite)
```sql
CREATE TABLE files (
    id INTEGER PRIMARY KEY,
    path TEXT UNIQUE,
    checksum TEXT,
    last_modified INTEGER,
    size INTEGER
);

CREATE TABLE symbols (
    id INTEGER PRIMARY KEY,
    file_id INTEGER,
    type TEXT,              -- 'function', 'class', 'method', 'constant'
    name TEXT,
    line_start INTEGER,
    line_end INTEGER,
    signature TEXT,
    docstring TEXT,
    FOREIGN KEY (file_id) REFERENCES files(id)
);

CREATE TABLE keywords (
    id INTEGER PRIMARY KEY,
    symbol_id INTEGER,
    keyword TEXT,
    weight REAL,
    FOREIGN KEY (symbol_id) REFERENCES symbols(id)
);

CREATE INDEX idx_keywords ON keywords(keyword);
CREATE INDEX idx_symbols_name ON symbols(name);
```

### Reference Implementation Format
```markdown
## Reference Implementation

Based on your story requirements, here are relevant existing implementations:

### 1. User Authentication (auth/login.py:45-67)
**Purpose:** Handles user login with JWT token generation
**Pattern:** POST endpoint with validation and error handling

```python
@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data['email']).first()
    
    if not user or not user.check_password(data['password']):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    token = generate_jwt(user.id)
    return jsonify({'token': token}), 200
```

**Key Patterns:**
- Input validation using get_json()
- Database query with SQLAlchemy
- Error responses with appropriate status codes
- JWT token generation for successful auth

---

### 2. Database Query Pattern (models/user.py:12-25)
**Purpose:** Shows how to safely query and validate user data
**Pattern:** Model method with error handling

```python
class User(db.Model):
    @classmethod
    def find_by_email(cls, email):
        if not email or '@' not in email:
            raise ValueError('Invalid email format')
        return cls.query.filter_by(email=email).first()
```

**Key Patterns:**
- Class method for reusable queries
- Input validation before database access
- Returns None if not found (not exception)

---

Use these patterns as reference when implementing your story.
```

### CLI Integration
```bash
# Add to bmad-phase.sh

phase_index() {
    local project_dir="${1:-.}"
    source "${SCRIPT_DIR}/lib/bmad-context.sh"
    
    log "INFO" "Indexing project: ${project_dir}"
    index_codebase "${project_dir}"
    
    if [[ $? -eq 0 ]]; then
        log "SUCCESS" "Indexing complete"
        show_index_stats "${project_dir}"
    else
        log "ERROR" "Indexing failed"
        return 1
    fi
}

phase_reindex() {
    local project_dir="${1:-.}"
    log "INFO" "Rebuilding index..."
    rm -rf "${project_dir}/.bmad/context-index"
    phase_index "${project_dir}"
}
```

### Configuration Example
```yaml
# .bmad/config.yaml

context:
  enabled: true
  
  # File patterns to index
  file_patterns:
    - "**/*.py"
    - "**/*.js"
    - "**/*.ts"
    - "**/*.go"
    - "**/*.java"
    - "**/*.rb"
  
  # Patterns to ignore
  ignore_patterns:
    - "**/node_modules/**"
    - "**/venv/**"
    - "**/.venv/**"
    - "**/dist/**"
    - "**/build/**"
    - "**/__pycache__/**"
    - "**/*.min.js"
    - "**/*.test.*"
  
  # Maximum results to return
  max_results: 5
  
  # Index staleness threshold (seconds)
  staleness_threshold: 3600
  
  # Minimum similarity score (0-1)
  min_similarity: 0.3
  
  # Debug mode
  debug: false
```

## Testing Requirements

### Unit Tests
```bash
# Test file scanner
test_scanner_respects_ignore_patterns
test_scanner_handles_binary_files
test_scanner_reports_progress

# Test parser
test_parser_extracts_python_functions
test_parser_extracts_javascript_classes
test_parser_handles_syntax_errors

# Test query
test_query_finds_relevant_code
test_query_ranks_by_similarity
test_query_handles_no_results
```

### Integration Tests
```bash
# Test full workflow
test_index_then_query_workflow
test_auto_refresh_on_file_change
test_mcp_tools_end_to_end

# Test with real projects
test_with_sample_python_project
test_with_sample_javascript_project
test_with_mixed_language_project
```

### Performance Tests
```bash
# Test scalability
test_index_1000_files_completes_under_30s
test_query_responds_under_1s
test_incremental_reindex_faster_than_full
```

## Dependencies

### Required
- `tree-sitter` or similar AST parsing library (for Python/JS/TS)
- `sqlite3` (for index storage)
- `jq` (JSON processing)
- `ripgrep` or `ag` (fast file searching)

### Optional
- `tree-sitter-python`, `tree-sitter-javascript` (language grammars)
- Python with `ast` module (for Python parsing)
- Node.js with `@babel/parser` (for JavaScript/TypeScript parsing)

## Migration Notes

### For Existing Projects
1. Run `bmad-phase index` to build initial index
2. Verify index with `bmad-phase search "your query"`
3. Test context retrieval with `bmad-phase develop story-key`
4. Adjust configuration if needed

### Backward Compatibility
- System works without index (graceful degradation)
- Existing stories continue to work
- MCP tools maintain same interface

## Future Enhancements (Not in Scope)

- Semantic search using embeddings (vs keyword-based)
- Cross-project context sharing
- Context learning from successful implementations
- Auto-suggest architectural patterns
- Integration with external documentation sources
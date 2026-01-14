#!/bin/bash
# BMAD Phase Runner - Run a single phase manually
# Usage: bmad-phase <phase> [story-key] [--project /path/to/project]
#
# Phases: create, develop, review, status, next

set -euo pipefail

# Use gtimeout on macOS, timeout on Linux
if command -v gtimeout &> /dev/null; then
    TIMEOUT_CMD="gtimeout"
elif command -v timeout &> /dev/null; then
    TIMEOUT_CMD="timeout"
else
    echo "Error: timeout command not found. Install coreutils: brew install coreutils"
    exit 1
fi

# Configuration
CLAUDE_MODEL="${CLAUDE_MODEL:-claude-sonnet-4-5-20250514}"
AIDER_MODEL="${AIDER_MODEL:-claude-sonnet-4-5-20250514}"
REVIEW_MODEL="${REVIEW_MODEL:-claude-opus-4-20250514}"
LLM_TIMEOUT="${LLM_TIMEOUT:-300}"

# Project paths
PROJECT_ROOT=""
SPRINT_STATUS=""
STORIES_DIR=""
EPICS_FILE=""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Initialize paths based on project root
init_paths() {
    local root="$1"

    if [[ ! -d "$root" ]]; then
        echo -e "${RED}Error: Project root does not exist: $root${NC}"
        exit 1
    fi

    PROJECT_ROOT="$(cd "$root" && pwd)"

    if [[ -f "$PROJECT_ROOT/docs/sprint-artifacts/sprint-status.yaml" ]]; then
        SPRINT_STATUS="$PROJECT_ROOT/docs/sprint-artifacts/sprint-status.yaml"
        STORIES_DIR="$PROJECT_ROOT/docs/sprint-artifacts"
    elif [[ -f "$PROJECT_ROOT/sprint-status.yaml" ]]; then
        SPRINT_STATUS="$PROJECT_ROOT/sprint-status.yaml"
        STORIES_DIR="$PROJECT_ROOT"
    else
        echo -e "${RED}Error: Cannot find sprint-status.yaml in project${NC}"
        exit 1
    fi

    if [[ -f "$PROJECT_ROOT/docs/epics.md" ]]; then
        EPICS_FILE="$PROJECT_ROOT/docs/epics.md"
    elif [[ -f "$PROJECT_ROOT/epics.md" ]]; then
        EPICS_FILE="$PROJECT_ROOT/epics.md"
    else
        echo -e "${RED}Error: Cannot find epics.md in project${NC}"
        exit 1
    fi
}

# Validate story key format
validate_story_key() {
    local key="$1"
    if [[ ! "$key" =~ ^[0-9]+-[0-9]+-[a-zA-Z0-9-]+$ ]]; then
        echo -e "${RED}Error: Invalid story key format: $key${NC}"
        echo "Expected format: N-N-slug (e.g., 0-1-homepage)"
        exit 1
    fi
}

# Get the default branch name
get_default_branch() {
    git -C "$PROJECT_ROOT" symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "main"
}

# Build context for LLM calls
build_context() {
    local context=""
    context+="=== SPRINT STATUS ===\n$(cat "$SPRINT_STATUS")\n\n"
    context+="=== EPICS ===\n$(cat "$EPICS_FILE")\n\n"

    for arch_file in "ARCHITECTURE_REALITY.md" "ARCHITECTURE.md" "docs/architecture.md"; do
        if [[ -f "$PROJECT_ROOT/$arch_file" ]]; then
            context+="=== ARCHITECTURE ===\n$(cat "$PROJECT_ROOT/$arch_file")\n\n"
            break
        fi
    done

    echo -e "$context"
}

# Phase: Create story
do_create() {
    local story_key="$1"
    validate_story_key "$story_key"

    echo -e "${BLUE}CREATE phase for: $story_key${NC}"
    echo "Using model: $CLAUDE_MODEL"
    echo "Timeout: ${LLM_TIMEOUT}s"

    local story_file="$STORIES_DIR/${story_key}.md"
    local context_file system_file prompt_file temp_file
    context_file=$(mktemp)
    system_file=$(mktemp)
    prompt_file=$(mktemp)
    temp_file=$(mktemp)

    build_context > "$context_file"

    cat > "$system_file" << SYSTEM_EOF
You are a BMAD Story Creator. Your job is to create comprehensive developer implementation guides.

Given the sprint status and epics file, create a complete story file for: $story_key

The story file MUST include:
1. Story header with title and status (ready-for-dev)
2. User story (As a... I want... So that...)
3. Acceptance Criteria in BDD format (Given/When/Then)
4. Detailed Tasks with checkboxes broken into subtasks
5. Technical requirements and file structure
6. Testing requirements

Output ONLY the markdown content for the story file. No explanations.
SYSTEM_EOF

    echo "Create a comprehensive story file for $story_key based on the context provided." > "$prompt_file"

    if $TIMEOUT_CMD "$LLM_TIMEOUT" bash -c \
        "cat '$context_file' | llm -m '$CLAUDE_MODEL' -s \"\$(cat '$system_file')\" \"\$(cat '$prompt_file')\"" \
        > "$temp_file" 2>&1; then

        if [[ -s "$temp_file" ]]; then
            mv "$temp_file" "$story_file"
            echo -e "${GREEN}✓ Story created: $story_file${NC}"

            # Update status
            yq -i ".development_status.\"$story_key\" = \"ready-for-dev\"" "$SPRINT_STATUS"
            echo -e "${GREEN}✓ Status updated to ready-for-dev${NC}"
        else
            echo -e "${RED}✗ LLM returned empty response${NC}"
            rm -f "$temp_file"
            exit 1
        fi
    else
        echo -e "${RED}✗ LLM call failed or timed out${NC}"
        rm -f "$temp_file"
        exit 1
    fi

    rm -f "$context_file" "$system_file" "$prompt_file"
}

# Phase: Develop story
do_develop() {
    local story_key="$1"
    validate_story_key "$story_key"

    echo -e "${BLUE}DEVELOP phase for: $story_key${NC}"

    local story_file="$STORIES_DIR/${story_key}.md"

    if [[ ! -f "$story_file" ]]; then
        echo -e "${RED}Error: Story file not found: $story_file${NC}"
        exit 1
    fi

    if command -v aider &> /dev/null; then
        echo "Using Aider (model: $AIDER_MODEL)..."
        cd "$PROJECT_ROOT"
        aider --model "$AIDER_MODEL" \
              --message "Implement the story in $story_file. Check off tasks as you complete them." \
              --no-auto-commits \
              --no-show-model-warnings
    elif command -v claude &> /dev/null; then
        echo "Using Claude Code..."
        cd "$PROJECT_ROOT"
        claude --print "Implement the story in $story_file. Check off tasks as you complete them."
    else
        echo -e "${YELLOW}No agentic tool found.${NC}"
        echo "Install one of:"
        echo "  pip install aider-chat"
        echo "  https://claude.ai/code"
        exit 1
    fi
}

# Phase: Review story
do_review() {
    local story_key="$1"
    validate_story_key "$story_key"

    echo -e "${BLUE}REVIEW phase for: $story_key${NC}"
    echo "Using model: $REVIEW_MODEL"
    echo "Timeout: ${LLM_TIMEOUT}s"

    local default_branch
    default_branch=$(get_default_branch)
    echo "Comparing against branch: $default_branch"

    local diff_content
    diff_content=$(cd "$PROJECT_ROOT" && git diff "$default_branch" --stat && git diff "$default_branch" 2>/dev/null) || {
        echo -e "${YELLOW}Warning: Could not get git diff${NC}"
        diff_content="No diff available"
    }

    local story_file="$STORIES_DIR/${story_key}.md"
    local story_content=""
    [[ -f "$story_file" ]] && story_content=$(cat "$story_file")

    local context_file system_file prompt_file
    context_file=$(mktemp)
    system_file=$(mktemp)
    prompt_file=$(mktemp)

    {
        echo "=== STORY REQUIREMENTS ==="
        echo "$story_content"
        echo ""
        echo "=== CODE CHANGES ==="
        echo "$diff_content"
    } > "$context_file"

    cat > "$system_file" << 'SYSTEM_EOF'
You are an ADVERSARIAL Senior Developer performing code review.

Your job is to find 3-10 specific issues in the code changes. You MUST find issues - 'looks good' is NOT acceptable.

Review for:
1. Code quality and patterns
2. Test coverage gaps
3. Security issues
4. Performance concerns
5. Acceptance criteria satisfaction

For each issue found:
- Describe the problem specifically
- Reference the file and line
- Suggest the fix
- Rate severity: CRITICAL, HIGH, MEDIUM, LOW

Output a structured review report.
SYSTEM_EOF

    echo "Perform adversarial code review for story: $story_key" > "$prompt_file"

    if $TIMEOUT_CMD "$LLM_TIMEOUT" bash -c \
        "cat '$context_file' | llm -m '$REVIEW_MODEL' -s \"\$(cat '$system_file')\" \"\$(cat '$prompt_file')\"" 2>&1; then
        echo ""
        echo -e "${GREEN}✓ Review complete${NC}"
    else
        echo -e "${RED}✗ Review failed or timed out${NC}"
        exit 1
    fi

    rm -f "$context_file" "$system_file" "$prompt_file"
}

# Phase: Show status
do_status() {
    echo -e "${BLUE}Sprint Status${NC}"
    echo ""
    yq -C ".development_status" "$SPRINT_STATUS"
}

# Phase: Show next actionable stories
do_next() {
    echo -e "${BLUE}Next Stories by Phase${NC}"
    echo ""

    echo -e "${YELLOW}Backlog (needs create):${NC}"
    yq -r '.development_status | to_entries | map(select(.value == "backlog" and (.key | test("^[0-9]+-[0-9]+")))) | .[0:3] | .[].key' "$SPRINT_STATUS" 2>/dev/null | sed 's/^/  /' || echo "  (none)"

    echo ""
    echo -e "${YELLOW}Ready for dev:${NC}"
    yq -r '.development_status | to_entries | map(select(.value == "ready-for-dev")) | .[0:3] | .[].key' "$SPRINT_STATUS" 2>/dev/null | sed 's/^/  /' || echo "  (none)"

    echo ""
    echo -e "${YELLOW}In progress:${NC}"
    yq -r '.development_status | to_entries | map(select(.value == "in-progress")) | .[0:3] | .[].key' "$SPRINT_STATUS" 2>/dev/null | sed 's/^/  /' || echo "  (none)"

    echo ""
    echo -e "${YELLOW}Needs review:${NC}"
    yq -r '.development_status | to_entries | map(select(.value == "review")) | .[0:3] | .[].key' "$SPRINT_STATUS" 2>/dev/null | sed 's/^/  /' || echo "  (none)"

    echo ""
    echo -e "${GREEN}Done:${NC}"
    local done_count
    done_count=$(yq -r '.development_status | to_entries | map(select(.value == "done")) | length' "$SPRINT_STATUS" 2>/dev/null || echo "0")
    echo "  $done_count stories completed"
}

# Show help
show_help() {
    echo "BMAD Phase Runner - Run single phases manually"
    echo ""
    echo "Usage: bmad-phase <phase> [story-key] [options]"
    echo ""
    echo "Phases:"
    echo "  create <key>   Create story file from epics"
    echo "  develop <key>  Implement story (aider/claude)"
    echo "  review <key>   Adversarial code review"
    echo "  status         Show sprint status"
    echo "  next           Show next actionable stories"
    echo ""
    echo "Options:"
    echo "  --project, -p PATH  Project root (default: current directory)"
    echo "  --help, -h          Show this help"
    echo ""
    echo "Environment variables:"
    echo "  CLAUDE_MODEL   Model for story creation (default: claude-sonnet-4-5-20250514)"
    echo "  AIDER_MODEL    Model for development (default: claude-sonnet-4-5-20250514)"
    echo "  REVIEW_MODEL   Model for code review (default: claude-opus-4-20250514)"
    echo "  LLM_TIMEOUT    Timeout in seconds (default: 300)"
    echo ""
    echo "Examples:"
    echo "  bmad-phase status"
    echo "  bmad-phase next"
    echo "  bmad-phase create 0-1-homepage"
    echo "  bmad-phase develop 0-1-homepage"
    echo "  bmad-phase review 0-1-homepage --project ~/myproject"
}

# Main
main() {
    local phase=""
    local story_key=""
    local project_path="."

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --project|-p)
                project_path="$2"
                shift 2
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            create|develop|review|status|next)
                phase="$1"
                shift
                ;;
            *)
                if [[ -z "$phase" ]]; then
                    echo -e "${RED}Error: Unknown phase: $1${NC}"
                    echo "Run 'bmad-phase --help' for usage"
                    exit 1
                else
                    story_key="$1"
                    shift
                fi
                ;;
        esac
    done

    if [[ -z "$phase" ]]; then
        show_help
        exit 0
    fi

    # Check dependencies
    for cmd in yq llm; do
        if ! command -v "$cmd" &> /dev/null; then
            echo -e "${RED}Error: $cmd is required but not installed${NC}"
            exit 1
        fi
    done

    # Initialize paths
    init_paths "$project_path"

    # Run phase
    case "$phase" in
        create)
            [[ -z "$story_key" ]] && { echo -e "${RED}Error: story-key required${NC}"; exit 1; }
            do_create "$story_key"
            ;;
        develop)
            [[ -z "$story_key" ]] && { echo -e "${RED}Error: story-key required${NC}"; exit 1; }
            do_develop "$story_key"
            ;;
        review)
            [[ -z "$story_key" ]] && { echo -e "${RED}Error: story-key required${NC}"; exit 1; }
            do_review "$story_key"
            ;;
        status)
            do_status
            ;;
        next)
            do_next
            ;;
    esac
}

main "$@"

#!/bin/bash
# BMAD Autopilot - Orchestrates story creation, development, and review
# Usage: bmad-autopilot [--project /path/to/project] [epic-number]
#
# Requires:
#   - llm CLI (https://github.com/simonw/llm) with plugins:
#     - llm-anthropic (for Claude)
#     - llm-gemini (for Gemini)
#   - tmux (optional, for dashboard mode)
#   - yq (for YAML parsing)
#   - Optional: aider or claude for development phase
#
# Expected project structure:
#   docs/
#     epics.md                    # Epic definitions
#     sprint-artifacts/
#       sprint-status.yaml        # Story status tracking
#       *.md                      # Story files
#       reviews/                  # Code review outputs

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

# Configuration - customize via environment variables
CLAUDE_MODEL="${CLAUDE_MODEL:-claude-sonnet-4-5-20250514}"
AIDER_MODEL="${AIDER_MODEL:-claude-sonnet-4-5-20250514}"
REVIEW_MODEL="${REVIEW_MODEL:-claude-opus-4-20250514}"
MAX_CONSECUTIVE_FAILURES=3
LLM_TIMEOUT="${LLM_TIMEOUT:-300}"
YOLO_MODE=false

# Project paths - set via --project flag or current directory
PROJECT_ROOT=""
SPRINT_STATUS=""
STORIES_DIR=""
EPICS_FILE=""
LOG_DIR=""

# Colors for output
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

    # Support multiple directory structures
    if [[ -f "$PROJECT_ROOT/docs/sprint-artifacts/sprint-status.yaml" ]]; then
        SPRINT_STATUS="$PROJECT_ROOT/docs/sprint-artifacts/sprint-status.yaml"
        STORIES_DIR="$PROJECT_ROOT/docs/sprint-artifacts"
    elif [[ -f "$PROJECT_ROOT/sprint-status.yaml" ]]; then
        SPRINT_STATUS="$PROJECT_ROOT/sprint-status.yaml"
        STORIES_DIR="$PROJECT_ROOT"
    else
        echo -e "${RED}Error: Cannot find sprint-status.yaml in project${NC}"
        echo "Expected locations:"
        echo "  - docs/sprint-artifacts/sprint-status.yaml"
        echo "  - sprint-status.yaml"
        exit 1
    fi

    # Find epics file
    if [[ -f "$PROJECT_ROOT/docs/epics.md" ]]; then
        EPICS_FILE="$PROJECT_ROOT/docs/epics.md"
    elif [[ -f "$PROJECT_ROOT/epics.md" ]]; then
        EPICS_FILE="$PROJECT_ROOT/epics.md"
    else
        echo -e "${RED}Error: Cannot find epics.md in project${NC}"
        exit 1
    fi

    LOG_DIR="$PROJECT_ROOT/logs/bmad-autopilot"
    mkdir -p "$LOG_DIR"
}

# Initialize logging with rotation
init_logging() {
    LOGFILE="$LOG_DIR/$(date +%Y%m%d-%H%M%S).log"
    # Keep only last 10 log files
    find "$LOG_DIR" -name "*.log" -type f 2>/dev/null | sort -r | tail -n +11 | xargs rm -f 2>/dev/null || true
}

log() {
    echo -e "[$(date '+%H:%M:%S')] $1" | tee -a "$LOGFILE"
}

log_phase() {
    echo -e "\n${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}\n"
}

# Validate story key format to prevent command injection
validate_story_key() {
    local key="$1"
    if [[ ! "$key" =~ ^[0-9]+-[0-9]+-[a-zA-Z0-9-]+$ ]]; then
        log "${RED}Invalid story key format: $key${NC}"
        log "Expected format: N-N-slug (e.g., 0-1-homepage)"
        return 1
    fi
    return 0
}

# Get the default branch name (main, master, etc.)
get_default_branch() {
    git -C "$PROJECT_ROOT" symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "main"
}

# Get next story to work on based on status
get_next_story() {
    local target_status="$1"

    local result
    result=$(yq -r ".development_status | to_entries |
        map(select(.key | test(\"^[0-9]+-[0-9]+\"))) |
        map(select(.value == \"$target_status\")) |
        .[0].key // \"\"" "$SPRINT_STATUS" 2>/dev/null)

    if [[ "$result" == "null" ]] || [[ -z "$result" ]]; then
        echo ""
    else
        echo "$result"
    fi
}

# Update story status in sprint-status.yaml with verification
update_status() {
    local story_key="$1"
    local new_status="$2"

    log "${YELLOW}Updating $story_key status to: $new_status${NC}"

    if ! yq -i ".development_status.\"$story_key\" = \"$new_status\"" "$SPRINT_STATUS"; then
        log "${RED}Failed to update status for $story_key${NC}"
        return 1
    fi

    local actual
    actual=$(yq -r ".development_status.\"$story_key\"" "$SPRINT_STATUS")
    if [[ "$actual" != "$new_status" ]]; then
        log "${RED}Status verification failed: expected $new_status, got $actual${NC}"
        return 1
    fi
}

# Check if all stories in an epic are done
check_epic_complete() {
    local epic_num="$1"

    local incomplete=$(yq -r ".development_status | to_entries |
        map(select(.key | test(\"^$epic_num-[0-9]+\"))) |
        map(select(.value != \"done\")) |
        length" "$SPRINT_STATUS")

    [[ "$incomplete" == "0" ]]
}

# Build context for LLM calls
build_context() {
    local context=""
    context+="=== SPRINT STATUS ===\n$(cat "$SPRINT_STATUS")\n\n"
    context+="=== EPICS ===\n$(cat "$EPICS_FILE")\n\n"

    # Add architecture if exists (check multiple locations)
    for arch_file in "ARCHITECTURE_REALITY.md" "ARCHITECTURE.md" "docs/architecture.md"; do
        if [[ -f "$PROJECT_ROOT/$arch_file" ]]; then
            context+="=== ARCHITECTURE ===\n$(cat "$PROJECT_ROOT/$arch_file")\n\n"
            break
        fi
    done

    # Add project context if exists
    for ctx_file in "docs/project_context.md" "PROJECT_CONTEXT.md" "README.md"; do
        if [[ -f "$PROJECT_ROOT/$ctx_file" ]]; then
            context+="=== PROJECT CONTEXT ===\n$(cat "$PROJECT_ROOT/$ctx_file")\n\n"
            break
        fi
    done

    echo -e "$context"
}

# Phase 1: Create Story (Claude)
create_story() {
    local story_key="$1"
    local story_file="$STORIES_DIR/${story_key}.md"

    log_phase "PHASE 1: CREATE STORY ($story_key)"

    if ! validate_story_key "$story_key"; then
        return 1
    fi

    log "Model: $CLAUDE_MODEL"

    # Backup existing story file if present
    if [[ -f "$story_file" ]]; then
        local backup_file="${story_file}.bak.$(date +%s)"
        cp "$story_file" "$backup_file"
        log "${YELLOW}Backed up existing story to: $backup_file${NC}"
    fi

    log "Generating story with Claude (timeout: ${LLM_TIMEOUT}s)..."

    local context_file prompt_file system_file temp_file
    context_file=$(mktemp)
    prompt_file=$(mktemp)
    system_file=$(mktemp)
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

    if ! $TIMEOUT_CMD "$LLM_TIMEOUT" bash -c \
        "cat '$context_file' | llm -m '$CLAUDE_MODEL' -s \"\$(cat '$system_file')\" \"\$(cat '$prompt_file')\"" \
        > "$temp_file" 2>> "$LOGFILE"; then
        local llm_exit_code=$?
        if [[ $llm_exit_code -eq 124 ]]; then
            log "${RED}✗ LLM call timed out after ${LLM_TIMEOUT}s${NC}"
        else
            log "${RED}✗ LLM API call failed with exit code $llm_exit_code${NC}"
        fi
        rm -f "$temp_file" "$context_file" "$prompt_file" "$system_file"
        return 1
    fi

    rm -f "$context_file" "$prompt_file" "$system_file"

    if [[ ! -s "$temp_file" ]]; then
        log "${RED}✗ LLM returned empty response${NC}"
        rm -f "$temp_file"
        return 1
    fi

    mv "$temp_file" "$story_file"

    log "${GREEN}✓ Story created: $story_file${NC}"
    update_status "$story_key" "ready-for-dev"
    return 0
}

# Phase 2: Develop Story
develop_story() {
    local story_key="$1"
    local story_file="$STORIES_DIR/${story_key}.md"

    log_phase "PHASE 2: DEVELOP STORY ($story_key)"

    if ! validate_story_key "$story_key"; then
        return 1
    fi

    log "Model: $AIDER_MODEL (or agentic tool)"

    if command -v aider &> /dev/null; then
        log "Using Aider for development..."

        local dev_prompt="Implement the story defined in $story_file

Read the story file carefully and implement ALL tasks and subtasks.
After each task, check it off in the story file.
Run tests to verify acceptance criteria.
When complete, update the story status to 'review'."

        cd "$PROJECT_ROOT"

        if $YOLO_MODE; then
            log "${RED}⚠ YOLO MODE: Auto-accepting all changes without review${NC}"
            aider --model "$AIDER_MODEL" \
                  --message "$dev_prompt" \
                  --yes-always \
                  --no-stream \
                  --no-show-model-warnings \
                  2>&1 | tee -a "$LOGFILE"
        else
            log "${YELLOW}NOTE: Aider requires interactive terminal for confirmations${NC}"
            log "${YELLOW}Use --yolo flag for fully unattended mode (accepts all changes)${NC}"
            aider --model "$AIDER_MODEL" \
                  --message "$dev_prompt" \
                  --no-auto-commits \
                  --no-show-model-warnings \
                  2>&1 | tee -a "$LOGFILE"
        fi

        update_status "$story_key" "review"
    elif command -v claude &> /dev/null; then
        log "Using Claude Code for development..."

        local instruction_file="/tmp/bmad-dev-instruction-$story_key.txt"
        cat > "$instruction_file" << EOF
Please implement the story in: $story_file

Read the story file and implement ALL tasks and subtasks listed.
Check off each task as you complete it.
Run tests to verify acceptance criteria are met.
When complete, update the sprint-status.yaml to set $story_key to 'review'.

Begin implementation now.
EOF

        log "${YELLOW}Starting Claude Code session...${NC}"
        log "Instruction: $instruction_file"

        cd "$PROJECT_ROOT"
        claude --print "$(<"$instruction_file")"

        local current_status=$(yq -r ".development_status.\"$story_key\"" "$SPRINT_STATUS")
        if [[ "$current_status" != "review" ]]; then
            log "${YELLOW}Manual update: Setting $story_key to 'review'${NC}"
            update_status "$story_key" "review"
        fi
    else
        log "${YELLOW}No agentic tool found. Manual development required.${NC}"
        log "Options:"
        log "  1. Install aider: pip install aider-chat"
        log "  2. Use Claude Code: claude (interactive)"
        log "  3. Develop manually and run: bmad-autopilot --continue"

        echo ""
        read -p "Press Enter when development is complete, or Ctrl+C to abort..."
        update_status "$story_key" "review"
    fi

    log "${GREEN}✓ Development phase complete${NC}"
}

# Phase 3: Code Review
review_story() {
    local story_key="$1"
    local story_file="$STORIES_DIR/${story_key}.md"

    log_phase "PHASE 3: CODE REVIEW ($story_key)"

    if ! validate_story_key "$story_key"; then
        return 1
    fi

    log "Model: $REVIEW_MODEL"

    local default_branch
    default_branch=$(get_default_branch)
    log "Comparing against branch: $default_branch"

    local diff_content
    diff_content=$(cd "$PROJECT_ROOT" && git diff "$default_branch" --stat && git diff "$default_branch") || {
        log "${YELLOW}Warning: Could not get git diff, using empty diff${NC}"
        diff_content="No diff available"
    }

    log "Running adversarial code review (timeout: ${LLM_TIMEOUT}s)..."
    local review_file="$STORIES_DIR/reviews/${story_key}-review.md"
    mkdir -p "$STORIES_DIR/reviews"

    local context_file prompt_file system_file temp_file
    context_file=$(mktemp)
    prompt_file=$(mktemp)
    system_file=$(mktemp)
    temp_file=$(mktemp)

    {
        echo "=== STORY REQUIREMENTS ==="
        [[ -f "$story_file" ]] && cat "$story_file"
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

    if ! $TIMEOUT_CMD "$LLM_TIMEOUT" bash -c \
        "cat '$context_file' | llm -m '$REVIEW_MODEL' -s \"\$(cat '$system_file')\" \"\$(cat '$prompt_file')\"" \
        > "$temp_file" 2>> "$LOGFILE"; then
        local exit_code=$?
        if [[ $exit_code -eq 124 ]]; then
            log "${RED}✗ Review timed out after ${LLM_TIMEOUT}s${NC}"
        else
            log "${RED}✗ Review API call failed with exit code $exit_code${NC}"
        fi
        rm -f "$temp_file" "$context_file" "$prompt_file" "$system_file"
        return 1
    fi

    rm -f "$context_file" "$prompt_file" "$system_file"

    if [[ ! -s "$temp_file" ]]; then
        log "${RED}✗ Review returned empty response${NC}"
        rm -f "$temp_file"
        return 1
    fi

    mv "$temp_file" "$review_file"
    log "${GREEN}✓ Review complete: $review_file${NC}"

    if grep -qi "CRITICAL" "$review_file"; then
        log "${RED}CRITICAL issues found - returning to development${NC}"
        update_status "$story_key" "in-progress"
        return 2
    else
        log "${GREEN}No critical issues - marking as done${NC}"
        update_status "$story_key" "done"
        return 0
    fi
}

# Main orchestration loop
run_autopilot() {
    local target_epic="${1:-}"

    log_phase "BMAD AUTOPILOT STARTED"
    log "Project: $PROJECT_ROOT"
    log "Sprint Status: $SPRINT_STATUS"
    log "Target Epic: ${target_epic:-all}"
    log "Log file: $LOGFILE"

    local iteration=0
    local max_iterations=50
    local consecutive_failures=0
    local last_failed_story=""

    while [[ $iteration -lt $max_iterations ]]; do
        ((iteration++))
        log "\n--- Iteration $iteration ---"

        # Check for backlog stories to create
        local backlog_story=$(get_next_story "backlog")
        if [[ -n "$backlog_story" ]]; then
            if [[ -n "$target_epic" ]] && [[ ! "$backlog_story" =~ ^$target_epic- ]]; then
                backlog_story=""
            fi
        fi

        if [[ -n "$backlog_story" ]]; then
            create_story "$backlog_story"
            continue
        fi

        # Check for ready-for-dev stories
        local ready_story=$(get_next_story "ready-for-dev")
        if [[ -n "$ready_story" ]]; then
            if [[ -n "$target_epic" ]] && [[ ! "$ready_story" =~ ^$target_epic- ]]; then
                ready_story=""
            fi
        fi

        if [[ -n "$ready_story" ]]; then
            develop_story "$ready_story"
            continue
        fi

        # Check for stories needing review
        local review_story=$(get_next_story "review")
        if [[ -n "$review_story" ]]; then
            if [[ -n "$target_epic" ]] && [[ ! "$review_story" =~ ^$target_epic- ]]; then
                review_story=""
            fi
        fi

        if [[ -n "$review_story" ]]; then
            review_story "$review_story"
            local review_result=$?

            if [[ $review_result -eq 0 ]]; then
                consecutive_failures=0
                last_failed_story=""
            elif [[ $review_result -eq 2 ]]; then
                consecutive_failures=0
                last_failed_story=""
            else
                if [[ "$review_story" == "$last_failed_story" ]]; then
                    ((consecutive_failures++))
                    if [[ $consecutive_failures -ge $MAX_CONSECUTIVE_FAILURES ]]; then
                        log "${RED}Skipping $review_story after $consecutive_failures consecutive API failures${NC}"
                        update_status "$review_story" "blocked"
                        consecutive_failures=0
                        last_failed_story=""
                    fi
                else
                    consecutive_failures=1
                    last_failed_story="$review_story"
                fi
            fi
            continue
        fi

        # Check for in-progress stories (resume development)
        local inprogress_story=$(get_next_story "in-progress")
        if [[ -n "$inprogress_story" ]]; then
            if [[ -n "$target_epic" ]] && [[ ! "$inprogress_story" =~ ^$target_epic- ]]; then
                inprogress_story=""
            fi
        fi

        if [[ -n "$inprogress_story" ]]; then
            develop_story "$inprogress_story"
            continue
        fi

        # No more work found
        log_phase "AUTOPILOT COMPLETE"

        if [[ -n "$target_epic" ]]; then
            if check_epic_complete "$target_epic"; then
                log "${GREEN}Epic $target_epic is COMPLETE!${NC}"
            else
                log "${YELLOW}No actionable stories found for epic $target_epic${NC}"
            fi
        else
            log "${GREEN}All stories processed!${NC}"
        fi

        break
    done

    if [[ $iteration -ge $max_iterations ]]; then
        log "${RED}Max iterations reached - possible infinite loop${NC}"
    fi
}

# Tmux session setup
setup_tmux() {
    local session_name="bmad-autopilot"

    tmux kill-session -t "$session_name" 2>/dev/null || true

    tmux new-session -d -s "$session_name" -n "main"

    # Layout:
    # ┌─────────────────────────────────────┐
    # │           Main Output               │
    # ├──────────────────┬──────────────────┤
    # │   Sprint Status  │   Log Tail       │
    # └──────────────────┴──────────────────┘

    tmux split-window -v -p 30 -t "$session_name"
    tmux split-window -h -p 50 -t "$session_name"

    tmux send-keys -t "$session_name:0.1" "watch -n 5 'yq -C \".development_status\" \"$SPRINT_STATUS\"'" C-m
    tmux send-keys -t "$session_name:0.2" "tail -f \"$LOGFILE\" 2>/dev/null || echo 'Waiting for log...'" C-m
    tmux select-pane -t "$session_name:0.0"

    log "Tmux session created: $session_name"
    log "Attach with: tmux attach -t $session_name"
}

# Entry point
main() {
    local epic_filter=""
    local use_tmux=false
    local continue_mode=false
    local project_path="."

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --project|-p)
                project_path="$2"
                shift 2
                ;;
            --epic|-e)
                epic_filter="$2"
                shift 2
                ;;
            --tmux|-t)
                use_tmux=true
                shift
                ;;
            --continue|-c)
                continue_mode=true
                shift
                ;;
            --yolo)
                YOLO_MODE=true
                shift
                ;;
            --help|-h)
                echo "BMAD Autopilot - Automated story development pipeline"
                echo ""
                echo "Usage: bmad-autopilot [options]"
                echo ""
                echo "Options:"
                echo "  --project, -p PATH  Project root directory (default: current directory)"
                echo "  --epic, -e NUM      Only process stories for epic NUM (e.g., 0, 1, 2)"
                echo "  --tmux, -t          Run in tmux session with status dashboard"
                echo "  --continue, -c      Continue from current state (skip already done)"
                echo "  --yolo              DANGER: Auto-accept all aider changes without review"
                echo "  --help, -h          Show this help"
                echo ""
                echo "Environment variables:"
                echo "  CLAUDE_MODEL        Model for story creation (default: claude-sonnet-4-5-20250514)"
                echo "  AIDER_MODEL         Model for development (default: claude-sonnet-4-5-20250514)"
                echo "  REVIEW_MODEL        Model for code review (default: claude-opus-4-20250514)"
                echo "  LLM_TIMEOUT         Timeout for LLM calls in seconds (default: 300)"
                echo ""
                echo "Expected project structure:"
                echo "  docs/"
                echo "    epics.md                    # Epic definitions"
                echo "    sprint-artifacts/"
                echo "      sprint-status.yaml        # Story status tracking"
                echo "      *.md                      # Story files"
                echo ""
                echo "Examples:"
                echo "  bmad-autopilot                        # Process all stories in current dir"
                echo "  bmad-autopilot --project ~/myproject  # Specify project"
                echo "  bmad-autopilot --epic 0               # Process only Epic 0 stories"
                echo "  bmad-autopilot --tmux                 # Run with tmux dashboard"
                exit 0
                ;;
            *)
                epic_filter="$1"
                shift
                ;;
        esac
    done

    # Check dependencies
    for cmd in yq llm; do
        if ! command -v "$cmd" &> /dev/null; then
            echo -e "${RED}Error: $cmd is required but not installed${NC}"
            echo "Install with:"
            echo "  yq: brew install yq"
            echo "  llm: pip install llm && llm install llm-anthropic llm-gemini"
            exit 1
        fi
    done

    # Initialize paths
    init_paths "$project_path"
    init_logging

    if $use_tmux; then
        setup_tmux
        local tmux_cmd="$(realpath "$0") --project \"$PROJECT_ROOT\" ${epic_filter:+--epic $epic_filter}"
        $YOLO_MODE && tmux_cmd+=" --yolo"
        tmux send-keys -t "bmad-autopilot:0.0" "$tmux_cmd" C-m
        tmux attach -t "bmad-autopilot"
    else
        run_autopilot "$epic_filter"
    fi
}

main "$@"

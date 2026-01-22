"""BMAD MCP Server - Orchestrates story creation, development, and code review."""

import json
import re
import subprocess
import tempfile
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .project import ProjectContext, validate_story_key
from .sprint import (
    get_development_status,
    get_status_summary,
    get_stories_by_status,
    get_stories_for_epic,
    get_next_story,
    update_story_status,
    VALID_STATUSES,
)
from .phases import (
    create_story,
    get_development_instructions,
    get_execution_instructions,
    plan_implementation,
    review_story,
)
from .phases.create import save_story
from .phases.review import save_review, get_git_diff
from .auto_fix import (
    ReviewIssueParser, 
    FixStrategyEngine, 
    FormattingStrategy, 
    AutoFixReport
)
from .auto_fix.modifier import CodeModifier
from .auto_fix.safety import SafetyGuard
from .auto_fix.reporter import ReportGenerator
from .auto_fix.validator import ValidationOrchestrator
from .context import ContextIndexer


# Global project context
ctx = ProjectContext()

# Create MCP server
server = Server("bmad-mcp")


def make_response(
    success: bool,
    data: Any = None,
    error: str | None = None,
    next_step: dict | None = None,
) -> dict:
    """Create standardized response with next_step guidance."""
    response = {
        "success": success,
        "data": data,
        "error": error,
    }
    if next_step:
        response["next_step"] = next_step
    return response


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available BMAD tools."""
    return [
        Tool(
            name="bmad_set_project",
            description="Set the active BMAD project directory. Must be called before other tools.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the BMAD project root directory",
                    },
                },
                "required": ["project_path"],
            },
        ),
        Tool(
            name="bmad_status",
            description="Get current sprint status with story counts by state.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="bmad_next",
            description="Get next actionable stories grouped by phase (backlog, ready-for-dev, in-progress, review).",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="bmad_create_story",
            description="Create a story file from the epics. Uses Claude to generate comprehensive implementation guide.",
            inputSchema={
                "type": "object",
                "properties": {
                    "story_key": {
                        "type": "string",
                        "description": "Story key in format N-N-slug (e.g., 0-1-homepage)",
                    },
                },
                "required": ["story_key"],
            },
        ),
        Tool(
            name="bmad_develop_story",
            description="Get story content with implementation instructions. YOU must then implement the code, check off tasks, and run tests.",
            inputSchema={
                "type": "object",
                "properties": {
                    "story_key": {
                        "type": "string",
                        "description": "Story key to develop",
                    },
                },
                "required": ["story_key"],
            },
        ),
        Tool(
            name="bmad_plan_implementation",
            description="Generate and validate a design plan for a story before execution.",
            inputSchema={
                "type": "object",
                "properties": {
                    "story_key": {
                        "type": "string",
                        "description": "Story key to plan",
                    },
                },
                "required": ["story_key"],
            },
        ),
        Tool(
            name="bmad_execute_implementation",
            description="Get execution instructions based on a validated design plan.",
            inputSchema={
                "type": "object",
                "properties": {
                    "story_key": {
                        "type": "string",
                        "description": "Story key to execute",
                    },
                },
                "required": ["story_key"],
            },
        ),
        Tool(
            name="bmad_verify_implementation",
            description="Verify implementation is complete before review. Checks git changes and task completion. Optionally runs tests.",
            inputSchema={
                "type": "object",
                "properties": {
                    "story_key": {
                        "type": "string",
                        "description": "Story key to verify",
                    },
                    "run_tests": {
                        "type": "boolean",
                        "description": "Whether to run tests (default: false for safety - tests execute project code)",
                        "default": False,
                    },
                },
                "required": ["story_key"],
            },
        ),
        Tool(
            name="bmad_review_story",
            description="Run adversarial code review on story changes. Call bmad_verify_implementation first to ensure you're ready.",
            inputSchema={
                "type": "object",
                "properties": {
                    "story_key": {
                        "type": "string",
                        "description": "Story key to review",
                    },
                },
                "required": ["story_key"],
            },
        ),
        Tool(
            name="bmad_update_status",
            description="Update a story's status in sprint-status.yaml.",
            inputSchema={
                "type": "object",
                "properties": {
                    "story_key": {
                        "type": "string",
                        "description": "Story key to update",
                    },
                    "status": {
                        "type": "string",
                        "description": "New status",
                        "enum": list(VALID_STATUSES),
                    },
                },
                "required": ["story_key", "status"],
            },
        ),
        Tool(
            name="bmad_run_epic",
            description="Get orchestration plan for running a full epic. Returns stories with their current status and recommended next actions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "epic_number": {
                        "type": "integer",
                        "description": "Epic number to run (e.g., 0, 1, 2)",
                    },
                },
                "required": ["epic_number"],
            },
        ),
        Tool(
            name="bmad_auto_fix",
            description="Automatically fix issues from code review. Parses the review file and applies formatting fixes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "story_key": {
                        "type": "string",
                        "description": "Story key to auto-fix (e.g., 0-1-homepage)",
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true, show what would be fixed without modifying files",
                        "default": False,
                    },
                },
                "required": ["story_key"],
            },
        ),
        Tool(
            name="bmad_index_project",
            description="Index the project codebase for context-aware development. Scans Python files and extracts functions/classes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "force": {
                        "type": "boolean",
                        "description": "Force reindex even if index exists",
                        "default": False,
                    },
                },
            },
        ),
        Tool(
            name="bmad_reindex",
            description="Force rebuild of the context index. Equivalent to bmad_index_project with force=true.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="bmad_search_context",
            description="Search indexed code for relevant implementations. Returns matching functions/classes with code snippets.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (keywords like 'user authentication login')",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 5)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    try:
        result = await _handle_tool(name, arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as e:
        error_response = make_response(False, error=str(e))
        return [TextContent(type="text", text=json.dumps(error_response, indent=2))]


async def _handle_tool(name: str, arguments: dict) -> dict:
    """Route tool calls to handlers."""

    if name == "bmad_set_project":
        return await handle_set_project(arguments["project_path"])

    # All other tools require project to be set
    if not ctx.is_set:
        return make_response(
            False,
            error="No project set. Use bmad_set_project first.",
            next_step={
                "action": "Set the project first",
                "tool": "bmad_set_project",
                "example": {"project_path": "~/Workspace/myproject"},
            },
        )

    if name == "bmad_status":
        return await handle_status()
    elif name == "bmad_next":
        return await handle_next()
    elif name == "bmad_create_story":
        return await handle_create_story(arguments["story_key"])
    elif name == "bmad_develop_story":
        return await handle_develop_story(arguments["story_key"])
    elif name == "bmad_plan_implementation":
        return await handle_plan_implementation(arguments["story_key"])
    elif name == "bmad_execute_implementation":
        return await handle_execute_implementation(arguments["story_key"])
    elif name == "bmad_verify_implementation":
        return await handle_verify_implementation(
            arguments["story_key"],
            run_tests=arguments.get("run_tests", False),
        )
    elif name == "bmad_review_story":
        return await handle_review_story(arguments["story_key"])
    elif name == "bmad_update_status":
        return await handle_update_status(
            arguments["story_key"],
            arguments["status"],
        )
    elif name == "bmad_run_epic":
        return await handle_run_epic(arguments["epic_number"])
    elif name == "bmad_auto_fix":
        return await handle_auto_fix(
            arguments["story_key"],
            dry_run=arguments.get("dry_run", False),
        )
    elif name == "bmad_index_project":
        return await handle_index_project(
            force=arguments.get("force", False),
        )
    elif name == "bmad_reindex":
        return await handle_index_project(force=True)
    elif name == "bmad_search_context":
        return await handle_search_context(
            arguments["query"],
            max_results=arguments.get("max_results", 5),
        )
    else:
        return make_response(False, error=f"Unknown tool: {name}")


async def handle_set_project(project_path: str) -> dict:
    """Handle bmad_set_project."""
    try:
        paths = ctx.set_project(project_path)
        summary = get_status_summary(paths.sprint_status)

        # Auto-index if needed
        indexer = ContextIndexer(project_root=paths.root)
        indexing_msg = ""
        if not indexer.is_indexed():
            stats = indexer.index()
            indexing_msg = f" (Auto-indexed {stats['files_indexed']} files)"
        elif indexer.is_stale():
            stats = indexer.index() # Refresh
            indexing_msg = f" (Refreshed index: {stats['files_indexed']} files)"

        return make_response(
            True,
            data={
                "project_root": str(paths.root),
                "sprint_status": str(paths.sprint_status),
                "epics_file": str(paths.epics_file),
                "stories_dir": str(paths.stories_dir),
                "status_summary": summary,
                "indexing_status": indexing_msg.strip(" ()"),
            },
            next_step={
                "action": "Check what needs to be done",
                "tool": "bmad_next",
                "description": "See which stories need work",
            },
        )
    except ValueError as e:
        return make_response(False, error=str(e))


async def handle_status() -> dict:
    """Handle bmad_status."""
    project = ctx.require_project()
    status = get_development_status(project.sprint_status)
    summary = get_status_summary(project.sprint_status)

    return make_response(
        True,
        data={
            "stories": status,
            "summary": summary,
        },
        next_step={
            "action": "See recommended next actions",
            "tool": "bmad_next",
        },
    )


async def handle_next() -> dict:
    """Handle bmad_next."""
    project = ctx.require_project()

    next_actions = {}
    for phase in ["backlog", "ready-for-dev", "planning", "executing", "in-progress", "review"]:
        stories = get_stories_by_status(project.sprint_status, phase)
        if stories:
            next_actions[phase] = stories[:3]

    recs = _build_recommendations(next_actions)

    # Determine the most important next step
    next_step = None
    if "review" in next_actions:
        next_step = {
            "action": "Review this story (it's blocking completion)",
            "tool": "bmad_review_story",
            "args": {"story_key": next_actions["review"][0]},
        }
    elif "executing" in next_actions:
        next_step = {
            "action": "Continue execution",
            "tool": "bmad_execute_implementation",
            "args": {"story_key": next_actions["executing"][0]},
        }
    elif "planning" in next_actions:
        next_step = {
            "action": "Continue planning",
            "tool": "bmad_plan_implementation",
            "args": {"story_key": next_actions["planning"][0]},
        }
    elif "in-progress" in next_actions:
        next_step = {
            "action": "Continue implementing this story",
            "tool": "bmad_develop_story",
            "args": {"story_key": next_actions["in-progress"][0]},
        }
    elif "ready-for-dev" in next_actions:
        next_step = {
            "action": "Start implementing this story",
            "tool": "bmad_develop_story",
            "args": {"story_key": next_actions["ready-for-dev"][0]},
        }
    elif "backlog" in next_actions:
        next_step = {
            "action": "Create this story first",
            "tool": "bmad_create_story",
            "args": {"story_key": next_actions["backlog"][0]},
        }

    return make_response(
        True,
        data={
            "next_actions": next_actions,
            "recommendations": recs,
        },
        next_step=next_step,
    )


def _build_recommendations(next_actions: dict) -> list[str]:
    """Build actionable recommendations."""
    recs = []

    if "review" in next_actions:
        recs.append(f"Review pending: {next_actions['review'][0]} - run bmad_review_story")
    if "executing" in next_actions:
        recs.append(f"Continue execution: {next_actions['executing'][0]} - run bmad_execute_implementation")
    if "planning" in next_actions:
        recs.append(f"Continue planning: {next_actions['planning'][0]} - run bmad_plan_implementation")
    if "in-progress" in next_actions:
        recs.append(f"Continue development: {next_actions['in-progress'][0]} - run bmad_develop_story")
    if "ready-for-dev" in next_actions:
        recs.append(f"Start development: {next_actions['ready-for-dev'][0]} - run bmad_develop_story")
    if "backlog" in next_actions:
        recs.append(f"Create story: {next_actions['backlog'][0]} - run bmad_create_story")

    return recs


async def handle_create_story(story_key: str) -> dict:
    """Handle bmad_create_story."""
    if not validate_story_key(story_key):
        return make_response(
            False,
            error=f"Invalid story key format: {story_key}. Expected N-N-slug.",
        )

    project = ctx.require_project()

    content = create_story(project, story_key)
    story_file = save_story(project, story_key, content)
    update_story_status(project.sprint_status, story_key, "ready-for-dev")

    return make_response(
        True,
        data={
            "story_key": story_key,
            "story_file": str(story_file),
            "content": content,
            "status": "ready-for-dev",
        },
        next_step={
            "action": "NOW IMPLEMENT THIS STORY - read the tasks and write the code",
            "tool": "bmad_develop_story",
            "args": {"story_key": story_key},
            "important": "After calling bmad_develop_story, YOU must write the actual code!",
        },
    )


async def handle_plan_implementation(story_key: str) -> dict:
    """Handle bmad_plan_implementation."""
    if not validate_story_key(story_key):
        return make_response(
            False,
            error=f"Invalid story key format: {story_key}. Expected N-N-slug.",
        )

    project = ctx.require_project()

    try:
        plan_data = plan_implementation(project, story_key)
        update_story_status(project.sprint_status, story_key, "planning")

        if plan_data.get("validation_passed"):
            next_step = {
                "action": "Proceed to execution using the validated plan",
                "tool": "bmad_execute_implementation",
                "args": {"story_key": story_key},
            }
        else:
            next_step = {
                "action": "Review validation report and update the plan",
                "tool": "bmad_plan_implementation",
                "args": {"story_key": story_key},
                "note": "Plan validation failed; fix the plan before execution.",
            }

        return make_response(
            True,
            data={
                **plan_data,
                "status": "planning",
            },
            next_step=next_step,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        return make_response(False, error=str(exc))


async def handle_develop_story(story_key: str) -> dict:
    """Handle bmad_develop_story."""
    if not validate_story_key(story_key):
        return make_response(
            False,
            error=f"Invalid story key format: {story_key}. Expected N-N-slug.",
        )

    project = ctx.require_project()

    try:
        instructions = get_development_instructions(project, story_key)

        validation_ok = instructions.get("validation_passed", True)
        if not validation_ok:
            update_story_status(project.sprint_status, story_key, "planning")
            return make_response(
                True,
                data={
                    **instructions,
                    "status": "planning",
                },
                next_step={
                    "action": "Fix the design plan and re-run planning",
                    "tool": "bmad_plan_implementation",
                    "args": {"story_key": story_key},
                },
            )

        update_story_status(project.sprint_status, story_key, "executing")

        # Count incomplete tasks
        incomplete_tasks = [t for t in instructions.get("tasks", []) if not t.get("completed")]

        return make_response(
            True,
            data={
                **instructions,
                "status": "executing",
                "incomplete_task_count": len(incomplete_tasks),
            },
            next_step={
                "action": "IMPLEMENT THE CODE NOW",
                "instructions": [
                    "1. Read the files listed in 'files' above (design_plan is your blueprint)",
                    "2. Implement EACH task from 'tasks' using TDD (test first, then code)",
                    "3. Check off tasks in the story file as you complete them ([ ] to [x])",
                    "4. Run tests to verify your implementation",
                    "5. Call bmad_verify_implementation when all tasks done",
                ],
                "then": {
                    "tool": "bmad_verify_implementation",
                    "args": {"story_key": story_key},
                },
                "warning": "Do NOT just read this - READ THE FILES and WRITE CODE!",
            },
        )
    except (FileNotFoundError, RuntimeError, ValueError) as e:
        return make_response(False, error=str(e))


async def handle_execute_implementation(story_key: str) -> dict:
    """Handle bmad_execute_implementation."""
    if not validate_story_key(story_key):
        return make_response(
            False,
            error=f"Invalid story key format: {story_key}. Expected N-N-slug.",
        )

    project = ctx.require_project()

    try:
        instructions = get_execution_instructions(project, story_key)
        update_story_status(project.sprint_status, story_key, "executing")

        incomplete_tasks = [t for t in instructions.get("tasks", []) if not t.get("completed")]

        return make_response(
            True,
            data={
                **instructions,
                "status": "executing",
                "incomplete_task_count": len(incomplete_tasks),
            },
            next_step={
                "action": "IMPLEMENT THE CODE NOW",
                "instructions": [
                    "1. Read the files listed in 'files' above (design_plan is your blueprint)",
                    "2. Implement EACH task from 'tasks' using TDD (test first, then code)",
                    "3. Check off tasks in the story file as you complete them ([ ] to [x])",
                    "4. Run tests to verify your implementation",
                    "5. Call bmad_verify_implementation when all tasks done",
                ],
                "then": {
                    "tool": "bmad_verify_implementation",
                    "args": {"story_key": story_key},
                },
                "warning": "Do NOT just read this - READ THE FILES and WRITE CODE!",
            },
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        return make_response(False, error=str(exc))


async def handle_verify_implementation(story_key: str, run_tests: bool = False) -> dict:
    """Handle bmad_verify_implementation - check if implementation is ready for review.

    Args:
        story_key: Story key to verify
        run_tests: Whether to run tests (opt-in for safety - tests execute project code)
    """
    if not validate_story_key(story_key):
        return make_response(
            False,
            error=f"Invalid story key format: {story_key}. Expected N-N-slug.",
        )

    project = ctx.require_project()
    issues = []

    # Check 1: Git has changes
    try:
        diff = get_git_diff(project.root)
        # Fix: Check for non-empty diff, not arbitrary 50 chars (prevents false negatives on small fixes)
        has_changes = diff and "No diff available" not in diff and len(diff.strip()) > 0
        if not has_changes:
            issues.append({
                "check": "git_changes",
                "passed": False,
                "message": "No git changes detected. Did you write and save the code?",
            })
        else:
            issues.append({
                "check": "git_changes",
                "passed": True,
                "message": f"Git changes detected ({len(diff)} chars)",
            })
    except Exception as e:
        issues.append({
            "check": "git_changes",
            "passed": False,
            "message": f"Could not check git: {e}",
        })

    # Check 2: Story file has checked tasks (only count ## Tasks section, not DoD/manual testing)
    story_file = project.stories_dir / f"{story_key}.md"
    if story_file.exists():
        content = story_file.read_text()

        # Extract only the Tasks section to avoid counting DoD, manual testing, etc.
        tasks_section = ""
        tasks_match = re.search(r'## Tasks\s*\n(.+?)(?=\n## |\Z)', content, re.DOTALL)
        if tasks_match:
            tasks_section = tasks_match.group(1)

        total_tasks = len(re.findall(r'- \[[ xX]\]', tasks_section))
        completed_tasks = len(re.findall(r'- \[[xX]\]', tasks_section))

        if total_tasks == 0:
            issues.append({
                "check": "task_completion",
                "passed": True,
                "message": "No checkbox tasks found in story",
            })
        elif completed_tasks == 0:
            issues.append({
                "check": "task_completion",
                "passed": False,
                "message": f"0/{total_tasks} tasks checked off. Update the story file!",
            })
        elif completed_tasks < total_tasks:
            issues.append({
                "check": "task_completion",
                "passed": False,
                "message": f"{completed_tasks}/{total_tasks} tasks completed. Finish remaining tasks.",
            })
        else:
            issues.append({
                "check": "task_completion",
                "passed": True,
                "message": f"All {total_tasks} tasks completed",
            })
    else:
        issues.append({
            "check": "task_completion",
            "passed": False,
            "message": "Story file not found",
        })

    # Check 3: Run tests (only if explicitly requested for safety)
    test_result = None
    if run_tests:
        # Detect test runner based on project files
        runner_cmd = None
        if (project.root / "package.json").exists():
            runner_cmd = ["npm", "test"]
        else:
            # Fallback to pytest for Python projects
            runner_cmd = ["pytest", "-q"]

        try:
            # Use temp files to prevent memory exhaustion from verbose test output
            with tempfile.TemporaryFile(mode='w+') as out_f, tempfile.TemporaryFile(mode='w+') as err_f:
                proc = subprocess.Popen(
                    runner_cmd,
                    cwd=project.root,
                    stdout=out_f,
                    stderr=err_f,
                    text=True
                )

                try:
                    proc.wait(timeout=60)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    test_result = {"check": "tests", "passed": None, "message": "Tests timed out"}

                if test_result is None:
                    if proc.returncode == 0:
                        test_result = {"check": "tests", "passed": True, "message": "Tests passed"}
                    else:
                        # Read TAIL of output for diagnostics (errors are at the end)
                        def read_tail(f, max_bytes=1000):
                            """Read last max_bytes from file."""
                            f.seek(0, 2)  # Seek to end
                            size = f.tell()
                            start = max(0, size - max_bytes)
                            f.seek(start)
                            return f.read()

                        stderr_tail = read_tail(err_f)
                        stdout_tail = read_tail(out_f)

                        # Build diagnostic message from last meaningful line
                        diagnostic = f"exit code {proc.returncode}"
                        if stderr_tail:
                            err_lines = [l.strip() for l in stderr_tail.split('\n') if l.strip()]
                            if err_lines:
                                diagnostic += f": {err_lines[-1][:100]}"
                        elif stdout_tail:
                            out_lines = [l.strip() for l in stdout_tail.split('\n') if l.strip()]
                            if out_lines:
                                diagnostic += f": {out_lines[-1][:100]}"

                        test_result = {
                            "check": "tests",
                            "passed": False,
                            "message": f"Tests failed ({diagnostic}) - fix before review"
                        }

        except FileNotFoundError:
            test_result = {"check": "tests", "passed": None, "message": f"Test runner '{runner_cmd[0]}' not found"}
        except Exception as e:
            test_result = {"check": "tests", "passed": None, "message": f"Could not run tests: {e}"}

        if test_result:
            issues.append(test_result)
    else:
        issues.append({
            "check": "tests",
            "passed": None,
            "message": "Tests skipped (use run_tests=true to execute)",
        })

    # Determine if ready for review
    failed_checks = [i for i in issues if i["passed"] is False]
    ready_for_review = len(failed_checks) == 0

    if ready_for_review:
        return make_response(
            True,
            data={
                "ready_for_review": True,
                "checks": issues,
            },
            next_step={
                "action": "Implementation verified! Now run the code review",
                "tool": "bmad_review_story",
                "args": {"story_key": story_key},
            },
        )
    else:
        return make_response(
            True,
            data={
                "ready_for_review": False,
                "checks": issues,
                "failed_checks": failed_checks,
            },
            next_step={
                "action": "FIX THESE ISSUES before review",
                "issues_to_fix": [i["message"] for i in failed_checks],
                "then": {
                    "tool": "bmad_verify_implementation",
                    "args": {"story_key": story_key},
                },
            },
        )


async def handle_review_story(story_key: str) -> dict:
    """Handle bmad_review_story with structured actionable feedback."""
    if not validate_story_key(story_key):
        return make_response(
            False,
            error=f"Invalid story key format: {story_key}. Expected N-N-slug.",
        )

    project = ctx.require_project()

    # Run review
    result = review_story(project, story_key)
    review_content = result["review"]

    # Issues are already parsed in review_story
    structured_issues = result.get("structured_issues", [])

    # Save review
    review_file = save_review(project, story_key, review_content)

    # Update status based on review
    new_status = result["recommendation"]
    update_story_status(project.sprint_status, story_key, new_status)

    if result["has_critical_issues"]:
        return make_response(
            True,
            data={
                "story_key": story_key,
                "review": review_content,
                "has_critical_issues": True,
                "structured_issues": structured_issues,
                "review_file": str(review_file),
                "new_status": new_status,
            },
            next_step={
                "action": "FIX THESE CRITICAL ISSUES",
                "issues": structured_issues,
                "instructions": [
                    "1. Fix each issue listed above",
                    "2. Pay special attention to CRITICAL and HIGH severity issues",
                    "3. Run tests after fixing",
                    "4. Call bmad_verify_implementation to check",
                    "5. Then call bmad_review_story again",
                ],
                "then": {
                    "tool": "bmad_verify_implementation",
                    "args": {"story_key": story_key},
                },
            },
        )
    else:
        return make_response(
            True,
            data={
                "story_key": story_key,
                "review": review_content,
                "has_critical_issues": False,
                "structured_issues": structured_issues,
                "review_file": str(review_file),
                "new_status": new_status,
            },
            next_step={
                "action": "Story complete! Move to next story",
                "tool": "bmad_next",
                "note": "The story is marked as done. Check for more work.",
            },
        )





async def handle_update_status(story_key: str, status: str) -> dict:
    """Handle bmad_update_status."""
    if not validate_story_key(story_key):
        return make_response(
            False,
            error=f"Invalid story key format: {story_key}. Expected N-N-slug.",
        )

    if status not in VALID_STATUSES:
        return make_response(
            False,
            error=f"Invalid status: {status}. Valid: {VALID_STATUSES}",
        )

    project = ctx.require_project()
    success = update_story_status(project.sprint_status, story_key, status)

    # Determine next step based on new status
    next_step = None
    if status == "review":
        next_step = {
            "action": "Run the code review",
            "tool": "bmad_review_story",
            "args": {"story_key": story_key},
        }
    elif status == "done":
        next_step = {
            "action": "Check for more work",
            "tool": "bmad_next",
        }
    elif status == "planning":
        next_step = {
            "action": "Continue planning",
            "tool": "bmad_plan_implementation",
            "args": {"story_key": story_key},
        }
    elif status == "executing":
        next_step = {
            "action": "Continue execution",
            "tool": "bmad_execute_implementation",
            "args": {"story_key": story_key},
        }
    elif status == "in-progress":
        next_step = {
            "action": "Continue implementation",
            "tool": "bmad_develop_story",
            "args": {"story_key": story_key},
        }

    return make_response(
        success,
        data={
            "story_key": story_key,
            "status": status,
        },
        next_step=next_step,
    )


async def handle_run_epic(epic_number: int) -> dict:
    """Handle bmad_run_epic."""
    project = ctx.require_project()

    stories = get_stories_for_epic(project.sprint_status, epic_number)

    if not stories:
        return make_response(
            False,
            error=f"No stories found for epic {epic_number}",
        )

    # Group by status
    by_status = {}
    for key, status in stories.items():
        by_status.setdefault(status, []).append(key)

    # Build orchestration plan
    plan = []

    for key in by_status.get("backlog", []):
        plan.append({
            "action": "create",
            "story_key": key,
            "tool": "bmad_create_story",
        })

    for key in by_status.get("ready-for-dev", []):
        plan.append({
            "action": "develop",
            "story_key": key,
            "tool": "bmad_develop_story",
        })

    for key in by_status.get("planning", []):
        plan.append({
            "action": "plan",
            "story_key": key,
            "tool": "bmad_plan_implementation",
        })

    for key in by_status.get("executing", []):
        plan.append({
            "action": "execute",
            "story_key": key,
            "tool": "bmad_execute_implementation",
        })

    for key in by_status.get("in-progress", []):
        plan.append({
            "action": "continue",
            "story_key": key,
            "tool": "bmad_develop_story",
        })

    for key in by_status.get("review", []):
        plan.append({
            "action": "review",
            "story_key": key,
            "tool": "bmad_review_story",
        })

    done_count = len(by_status.get("done", []))
    total_count = len(stories)

    # Get the first action from plan
    next_step = None
    if plan:
        first = plan[0]
        next_step = {
            "action": f"{first['action'].upper()} this story first",
            "tool": first["tool"],
            "args": {"story_key": first["story_key"]},
            "remaining_steps": len(plan) - 1,
        }
    elif done_count == total_count:
        next_step = {
            "action": "Epic complete! All stories are done.",
            "tool": "bmad_next",
            "note": "Check if there are other epics to work on",
        }

    return make_response(
        True,
        data={
            "epic_number": epic_number,
            "stories": stories,
            "by_status": by_status,
            "plan": plan,
            "progress": f"{done_count}/{total_count} stories done",
            "is_complete": done_count == total_count,
        },
        next_step=next_step,
    )


async def handle_auto_fix(story_key: str, dry_run: bool = False) -> dict:
    """Handle bmad_auto_fix - automatically fix issues from code review.

    Args:
        story_key: Story key to auto-fix
        dry_run: If True, show what would be fixed without modifying files
    """
    if not validate_story_key(story_key) or "/" in story_key or "\\" in story_key or ".." in story_key:
        return make_response(
            False,
            error=f"Invalid story key format: {story_key}. Expected N-N-slug.",
        )

    project = ctx.require_project()

    # Load configuration
    from .auto_fix.config import load_config, StrategyConfig
    config = load_config(project.root)

    # Safety Check: Ensure clean git state before applying fixes
    safety = SafetyGuard(project.root)
    if not dry_run and config.require_clean_git and not safety.check_git_status():
        return make_response(
            False,
            error="Working directory is not clean. Commit or stash changes before running auto-fix to prevent data loss.",
            next_step={
                "action": "Check git status",
                "tool": "run_shell_command",
                "args": {"command": "git status"},
            },
        )

    # Find the review file
    reviews_dir = project.stories_dir / "reviews"
    review_file = reviews_dir / f"{story_key}-review.md"

    if not review_file.exists():
        return make_response(
            False,
            error=f"Review file not found: {review_file}. Run bmad_review_story first.",
            next_step={
                "action": "Run code review first",
                "tool": "bmad_review_story",
                "args": {"story_key": story_key},
            },
        )

    # Parse the review
    parser = ReviewIssueParser(project_root=project.root)
    issues = parser.parse_file(review_file)

    if not issues:
        return make_response(
            True,
            data={
                "story_key": story_key,
                "message": "No issues found in review",
                "fixed_count": 0,
                "failed_count": 0,
            },
            next_step={
                "action": "Story may be complete",
                "tool": "bmad_update_status",
                "args": {"story_key": story_key, "status": "done"},
            },
        )

    # Set up the engine with formatting strategy
    engine = FixStrategyEngine(project_root=project.root, dry_run=dry_run)
    
    if config.strategies.get("formatting", StrategyConfig()).enabled:
        engine.register_strategy(FormattingStrategy())
        
    # TODO: Register other strategies when implemented
    # if config.strategies.get("imports", StrategyConfig()).enabled:
    #     engine.register_strategy(ImportStrategy())

    # Run fixes
    results = engine.fix_issues(issues)

    # Build report
    report = AutoFixReport(story_key=story_key, results=results)
    
    # Validation (Re-run tests)
    validation_passed = None
    if not dry_run and report.fixed_count > 0:
        validator = ValidationOrchestrator(project.root)
        validation_passed = validator.run_tests()

    # Generate Markdown Report
    reporter = ReportGenerator()
    report_file = reporter.save_report(report, reviews_dir)

    # Determine next step based on results
    next_step = None
    if dry_run:
        next_step = {
            "action": "Review planned fixes and run with dry_run=False",
            "tool": "bmad_auto_fix",
            "args": {"story_key": story_key, "dry_run": False},
        }
    elif validation_passed:
        next_step = {
            "action": "Fixes verified! Review report and complete story.",
            "tool": "bmad_update_status",
            "args": {"story_key": story_key, "status": "done"},
        }
    elif validation_passed is False:
        next_step = {
            "action": "Fixes applied but tests failed. Check report.",
            "tool": "run_shell_command",
            "args": {"command": f"cat {report_file}"},
        }
    elif report.failed_count > 0 or report.skipped_count > 0:
        next_step = {
            "action": "Manual fixes needed",
            "remaining_issues": [
                {"severity": r.issue.severity, "problem": r.issue.problem, "file": r.issue.file}
                for r in results if r.status != "success" and r.status != "dry_run"
            ],
        }
    else:
        next_step = {
            "action": "No auto-fixes needed",
            "tool": "bmad_verify_implementation",
            "args": {"story_key": story_key},
        }

    return make_response(
        True,
        data={
            "story_key": story_key,
            "dry_run": dry_run,
            "report_file": str(report_file),
            "total_issues": report.total_issues,
            "fixed_count": report.fixed_count,
            "dry_run_count": report.dry_run_count,
            "failed_count": report.failed_count,
            "validation_passed": validation_passed,
            "results": [
                {
                    "status": r.status,
                    "severity": r.issue.severity,
                    "problem": r.issue.problem,
                    "file": r.issue.file,
                    "changes": r.changes,
                    "error": r.error_message,
                }
                for r in results
            ],
        },
        next_step=next_step,
    )


async def handle_index_project(force: bool = False) -> dict:
    """Handle bmad_index_project - index codebase for context retrieval.

    Args:
        force: If True, reindex even if index exists
    """
    project = ctx.require_project()

    indexer = ContextIndexer(project_root=project.root)

    # Check if already indexed
    if indexer.is_indexed() and not force:
        metadata = indexer.get_metadata()
        return make_response(
            True,
            data={
                "already_indexed": True,
                "files_indexed": metadata.files_indexed if metadata else 0,
                "symbols_indexed": metadata.symbols_indexed if metadata else 0,
                "message": "Index already exists. Use force=true to reindex.",
            },
            next_step={
                "action": "Search the index",
                "tool": "bmad_search_context",
                "example": {"query": "authentication login user"},
            },
        )

    # Run indexing
    stats = indexer.index(force=force)

    return make_response(
        True,
        data={
            "indexed": True,
            "files_indexed": stats["files_indexed"],
            "symbols_indexed": stats["symbols_indexed"],
            "index_dir": stats["index_dir"],
        },
        next_step={
            "action": "Search the index",
            "tool": "bmad_search_context",
            "example": {"query": "authentication login user"},
        },
    )


async def handle_search_context(query: str, max_results: int = 5) -> dict:
    """Handle bmad_search_context - search indexed code.

    Args:
        query: Search query string
        max_results: Maximum number of results
    """
    project = ctx.require_project()

    indexer = ContextIndexer(project_root=project.root)

    # Check if indexed
    if not indexer.is_indexed():
        return make_response(
            False,
            error="Project not indexed. Run bmad_index_project first.",
            next_step={
                "action": "Index the project first",
                "tool": "bmad_index_project",
            },
        )

    # Search
    results = indexer.search(query, max_results)

    if not results:
        return make_response(
            True,
            data={
                "query": query,
                "results": [],
                "message": "No matching code found",
            },
        )

    # Format results with code snippets
    formatted_results = []
    for entry in results:
        file_path = project.root / entry.file_path
        snippet = ""
        if file_path.exists():
            try:
                lines = file_path.read_text().split("\n")
                start = max(0, entry.line_start - 1)
                end = min(len(lines), entry.line_end)
                snippet = "\n".join(lines[start:end])
            except Exception:
                pass

        formatted_results.append({
            "file": entry.file_path,
            "symbol": entry.symbol_name,
            "type": entry.symbol_type,
            "lines": f"{entry.line_start}-{entry.line_end}",
            "signature": entry.signature,
            "docstring": entry.docstring,
            "snippet": snippet[:500] if snippet else None,
        })

    return make_response(
        True,
        data={
            "query": query,
            "results": formatted_results,
            "count": len(formatted_results),
        },
    )


def main():
    """Run the MCP server."""
    import asyncio

    async def run():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(run())


if __name__ == "__main__":
    main()

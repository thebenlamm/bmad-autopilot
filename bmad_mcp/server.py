"""BMAD MCP Server - Orchestrates story creation, development, and code review."""

import json
import re
import subprocess
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
from .phases import create_story, get_development_instructions, review_story
from .phases.create import save_story
from .phases.review import save_review, get_git_diff


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
    else:
        return make_response(False, error=f"Unknown tool: {name}")


async def handle_set_project(project_path: str) -> dict:
    """Handle bmad_set_project."""
    try:
        paths = ctx.set_project(project_path)
        summary = get_status_summary(paths.sprint_status)

        return make_response(
            True,
            data={
                "project_root": str(paths.root),
                "sprint_status": str(paths.sprint_status),
                "epics_file": str(paths.epics_file),
                "stories_dir": str(paths.stories_dir),
                "status_summary": summary,
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
    for phase in ["backlog", "ready-for-dev", "in-progress", "review"]:
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
        update_story_status(project.sprint_status, story_key, "in-progress")

        # Count incomplete tasks
        incomplete_tasks = [t for t in instructions.get("tasks", []) if not t.get("completed")]

        return make_response(
            True,
            data={
                **instructions,
                "status": "in-progress",
                "incomplete_task_count": len(incomplete_tasks),
            },
            next_step={
                "action": "IMPLEMENT THE CODE NOW",
                "instructions": [
                    "1. Read the story_content and tasks above",
                    "2. Write code to implement EACH task in the target project",
                    "3. Check off tasks in the story file as you complete them (change [ ] to [x])",
                    "4. Run tests manually to verify your implementation",
                    "5. When done, call bmad_verify_implementation to check your work",
                    "   (add run_tests=true if you trust the project's test suite)",
                ],
                "then": {
                    "tool": "bmad_verify_implementation",
                    "args": {"story_key": story_key},
                },
                "warning": "Do NOT just read this and move on - you must WRITE CODE!",
            },
        )
    except FileNotFoundError as e:
        return make_response(False, error=str(e))


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
        has_changes = diff and "No diff available" not in diff and len(diff.strip()) > 50
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

    # Check 2: Story file has checked tasks
    story_file = project.stories_dir / f"{story_key}.md"
    if story_file.exists():
        content = story_file.read_text()
        total_tasks = len(re.findall(r'- \[[ xX]\]', content))
        completed_tasks = len(re.findall(r'- \[[xX]\]', content))

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
    # Tests execute project code, which could be malicious in untrusted repos
    test_result = None
    if run_tests:
        try:
            result = subprocess.run(
                ["npm", "test"],
                cwd=project.root,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                test_result = {"check": "tests", "passed": True, "message": "Tests passed"}
            else:
                test_result = {"check": "tests", "passed": False, "message": "Tests failed - fix before review"}
        except FileNotFoundError:
            # npm not found, try pytest
            try:
                result = subprocess.run(
                    ["pytest", "-q"],
                    cwd=project.root,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.returncode == 0:
                    test_result = {"check": "tests", "passed": True, "message": "Tests passed"}
                else:
                    test_result = {"check": "tests", "passed": False, "message": "Tests failed - fix before review"}
            except FileNotFoundError:
                test_result = {"check": "tests", "passed": None, "message": "No test runner found (npm/pytest)"}
        except subprocess.TimeoutExpired:
            test_result = {"check": "tests", "passed": None, "message": "Tests timed out - manual verification needed"}
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
    # passed=None means skipped/unknown, which doesn't block review
    # passed=False means failed, which blocks review
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

    # Parse structured issues from review
    structured_issues = _parse_review_issues(review_content)

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


def _parse_review_issues(review_content: str) -> list[dict]:
    """Parse structured issues from review markdown."""
    issues = []

    # Pattern: Look for severity markers and extract context
    severity_pattern = r'\*\*(CRITICAL|HIGH|MEDIUM|LOW)\*\*[:\s]*(.+?)(?=\*\*(?:CRITICAL|HIGH|MEDIUM|LOW)\*\*|$)'

    for match in re.finditer(severity_pattern, review_content, re.DOTALL | re.IGNORECASE):
        severity = match.group(1).upper()
        content = match.group(2).strip()

        # Try to extract file reference
        file_match = re.search(r'[`\']?([a-zA-Z0-9_/.-]+\.[a-zA-Z]+)[`\']?(?::(\d+))?', content)
        file_path = file_match.group(1) if file_match else None
        line_num = file_match.group(2) if file_match and file_match.group(2) else None

        # Get first line as problem summary
        lines = content.split('\n')
        problem = lines[0].strip() if lines else content[:100]

        # Look for suggested fix
        fix_match = re.search(r'(?:fix|solution|suggest|change)[:\s]*(.+?)(?:\n|$)', content, re.IGNORECASE)
        fix = fix_match.group(1).strip() if fix_match else None

        issues.append({
            "severity": severity,
            "problem": problem,
            "file": file_path,
            "line": int(line_num) if line_num else None,
            "suggested_fix": fix,
            "full_context": content[:500],
        })

    # If no structured issues found, create a generic one
    if not issues and review_content:
        has_critical = "CRITICAL" in review_content.upper()
        issues.append({
            "severity": "CRITICAL" if has_critical else "MEDIUM",
            "problem": "Review found issues - see full review content",
            "file": None,
            "line": None,
            "suggested_fix": None,
            "full_context": review_content[:500],
        })

    return issues


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


def main():
    """Run the MCP server."""
    import asyncio

    async def run():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(run())


if __name__ == "__main__":
    main()

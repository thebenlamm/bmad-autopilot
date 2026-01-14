"""BMAD MCP Server - Orchestrates story creation, development, and code review."""

import json
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
from .phases.review import save_review


# Global project context
ctx = ProjectContext()

# Create MCP server
server = Server("bmad-mcp")


def make_response(success: bool, data: Any = None, error: str | None = None) -> dict:
    """Create standardized response."""
    return {
        "success": success,
        "data": data,
        "error": error,
    }


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
            description="Get story content with implementation instructions. Returns tasks for you to implement directly.",
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
            name="bmad_review_story",
            description="Run adversarial code review on story changes. Compares git diff against story requirements.",
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
        )

    if name == "bmad_status":
        return await handle_status()
    elif name == "bmad_next":
        return await handle_next()
    elif name == "bmad_create_story":
        return await handle_create_story(arguments["story_key"])
    elif name == "bmad_develop_story":
        return await handle_develop_story(arguments["story_key"])
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

        return make_response(True, data={
            "project_root": str(paths.root),
            "sprint_status": str(paths.sprint_status),
            "epics_file": str(paths.epics_file),
            "stories_dir": str(paths.stories_dir),
            "status_summary": summary,
        })
    except ValueError as e:
        return make_response(False, error=str(e))


async def handle_status() -> dict:
    """Handle bmad_status."""
    project = ctx.require_project()
    status = get_development_status(project.sprint_status)
    summary = get_status_summary(project.sprint_status)

    return make_response(True, data={
        "stories": status,
        "summary": summary,
    })


async def handle_next() -> dict:
    """Handle bmad_next."""
    project = ctx.require_project()

    next_actions = {}
    for phase in ["backlog", "ready-for-dev", "in-progress", "review"]:
        stories = get_stories_by_status(project.sprint_status, phase)
        if stories:
            next_actions[phase] = stories[:3]  # Top 3 per phase

    return make_response(True, data={
        "next_actions": next_actions,
        "recommendations": _build_recommendations(next_actions),
    })


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

    # Create story content
    content = create_story(project, story_key)

    # Save to file
    story_file = save_story(project, story_key, content)

    # Update status
    update_story_status(project.sprint_status, story_key, "ready-for-dev")

    return make_response(True, data={
        "story_key": story_key,
        "story_file": str(story_file),
        "content": content,
        "status": "ready-for-dev",
    })


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

        # Update status to in-progress
        update_story_status(project.sprint_status, story_key, "in-progress")

        return make_response(True, data={
            **instructions,
            "status": "in-progress",
        })
    except FileNotFoundError as e:
        return make_response(False, error=str(e))


async def handle_review_story(story_key: str) -> dict:
    """Handle bmad_review_story."""
    if not validate_story_key(story_key):
        return make_response(
            False,
            error=f"Invalid story key format: {story_key}. Expected N-N-slug.",
        )

    project = ctx.require_project()

    # Run review
    result = review_story(project, story_key)

    # Save review
    review_file = save_review(project, story_key, result["review"])

    # Update status based on review
    new_status = result["recommendation"]
    update_story_status(project.sprint_status, story_key, new_status)

    return make_response(True, data={
        **result,
        "review_file": str(review_file),
        "new_status": new_status,
    })


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

    return make_response(success, data={
        "story_key": story_key,
        "status": status,
    })


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

    # 1. Create stories from backlog
    for key in by_status.get("backlog", []):
        plan.append({
            "action": "create",
            "story_key": key,
            "tool": "bmad_create_story",
        })

    # 2. Develop ready-for-dev stories
    for key in by_status.get("ready-for-dev", []):
        plan.append({
            "action": "develop",
            "story_key": key,
            "tool": "bmad_develop_story",
        })

    # 3. Continue in-progress stories
    for key in by_status.get("in-progress", []):
        plan.append({
            "action": "continue",
            "story_key": key,
            "tool": "bmad_develop_story",
        })

    # 4. Review stories pending review
    for key in by_status.get("review", []):
        plan.append({
            "action": "review",
            "story_key": key,
            "tool": "bmad_review_story",
        })

    done_count = len(by_status.get("done", []))
    total_count = len(stories)

    return make_response(True, data={
        "epic_number": epic_number,
        "stories": stories,
        "by_status": by_status,
        "plan": plan,
        "progress": f"{done_count}/{total_count} stories done",
        "is_complete": done_count == total_count,
    })


def main():
    """Run the MCP server."""
    import asyncio

    async def run():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(run())


if __name__ == "__main__":
    main()

"""Development phase - orchestrates planning + execution.

Returns lean responses with file paths only. Claude Code reads files directly.
"""

from ..project import ProjectPaths
from .plan import plan_implementation
from .execute import get_execution_instructions


def get_development_instructions(project: ProjectPaths, story_key: str) -> dict:
    """Get development instructions for a story.

    Runs the planning phase first. If validation passes, returns execution
    instructions with file paths. If validation fails, returns planning
    outputs so the user can revise the plan.

    Returns file paths only - no embedded file content.
    """
    plan_data = plan_implementation(project, story_key)
    if not plan_data.get("validation_passed"):
        plan_data["instructions"] = _build_plan_fix_instructions(story_key, plan_data)
        return plan_data

    execution_data = get_execution_instructions(project, story_key)

    # Merge file paths from both phases
    merged_files = {
        **plan_data.get("files", {}),
        **execution_data.get("files", {}),
    }

    return {
        "story_key": story_key,
        "files": merged_files,
        "tasks": execution_data.get("tasks", []),
        "validation_passed": True,
        "instructions": execution_data.get("instructions", ""),
    }


def _build_plan_fix_instructions(story_key: str, plan_data: dict) -> str:
    """Build instructions when validation fails."""
    files = plan_data.get("files", {})
    return (
        "## Planning Instructions\n\n"
        "The design plan validation failed. Review the validation report, revise the "
        "design plan, and re-run bmad_plan_implementation before executing.\n\n"
        f"Design plan file: {files.get('design_plan')}\n"
        f"Validation report: {files.get('validation_report')}\n"
        f"Story key: {story_key}\n"
    )

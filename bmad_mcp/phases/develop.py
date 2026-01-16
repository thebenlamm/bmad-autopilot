"""Development phase - orchestrates planning + execution."""

from ..project import ProjectPaths
from .plan import plan_implementation
from .execute import get_execution_instructions


def get_development_instructions(project: ProjectPaths, story_key: str) -> dict:
    """Get development instructions for a story.

    Runs the planning phase first. If validation passes, returns execution
    instructions that embed the design plan. If validation fails, returns
    planning outputs so the user can revise the plan.
    """
    plan_data = plan_implementation(project, story_key)
    if not plan_data.get("validation_passed"):
        plan_data["instructions"] = _build_plan_fix_instructions(story_key, plan_data)
        return plan_data

    execution_data = get_execution_instructions(project, story_key)
    return {
        **plan_data,
        **execution_data,
    }


def _build_plan_fix_instructions(story_key: str, plan_data: dict) -> str:
    """Build instructions when validation fails."""
    return (
        "## Planning Instructions\n\n"
        "The design plan validation failed. Review the validation report, revise the "
        "design plan, and re-run bmad_plan_implementation before executing.\n\n"
        f"Design plan file: {plan_data.get('design_plan_file')}\n"
        f"Validation report: {plan_data.get('validation_report_file')}\n"
        f"Story key: {story_key}\n"
    )

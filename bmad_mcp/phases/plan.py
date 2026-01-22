"""Planning phase - generate and validate a design plan.

Returns lean responses with file paths only. Claude Code reads files directly.
"""

from ..planning.generator import generate_design_plan, save_design_plan
from ..planning.validator import (
    validate_design_plan,
    save_validation_report,
    validation_passed,
)
from ..project import ProjectPaths


def plan_implementation(project: ProjectPaths, story_key: str) -> dict:
    """Generate and validate a design plan for a story.

    Returns file paths only - no embedded file content.
    Claude Code should read the referenced files directly.
    """
    plan_content = generate_design_plan(project, story_key)
    plan_file = save_design_plan(project, story_key, plan_content)

    validation_report = validate_design_plan(project, story_key, plan_content)
    validation_file = save_validation_report(project, story_key, validation_report)

    passed = validation_passed(validation_report)

    return {
        "story_key": story_key,
        "files": {
            "design_plan": str(plan_file),
            "validation_report": str(validation_file),
        },
        "validation_passed": passed,
    }

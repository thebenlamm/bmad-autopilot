"""Execution phase - provide implementation instructions from a validated plan."""

from ..context import ContextRetriever
from ..planning import get_story_artifact_dir
from ..planning.validator import validation_passed
from ..project import ProjectPaths


def get_execution_instructions(project: ProjectPaths, story_key: str) -> dict:
    """Get execution instructions for a story based on its design plan."""
    story_file = project.stories_dir / f"{story_key}.md"
    if not story_file.exists():
        raise FileNotFoundError(f"Story file not found: {story_file}")

    story_dir = get_story_artifact_dir(project, story_key)
    plan_file = story_dir / "design-plan.md"
    report_file = story_dir / "validation-report.md"

    if not plan_file.exists():
        raise FileNotFoundError(f"Design plan not found: {plan_file}")
    if not report_file.exists():
        raise FileNotFoundError(f"Validation report not found: {report_file}")

    design_plan = plan_file.read_text()
    validation_report = report_file.read_text()
    if not validation_passed(validation_report):
        raise ValueError("Design plan validation failed; fix plan before execution.")

    story_content = story_file.read_text()
    tasks = _extract_tasks(story_content)

    retriever = ContextRetriever(project.root)
    context_section = ""
    try:
        context_section = retriever.retrieve_formatted(story_content)
    except Exception as exc:
        context_section = f"<!-- Context retrieval failed: {exc} -->"

    instructions = _build_execution_instructions(
        story_key=story_key,
        project=project,
        design_plan=design_plan,
        validation_report=validation_report,
        context=context_section,
    )

    return {
        "story_key": story_key,
        "story_file": str(story_file),
        "story_content": story_content,
        "tasks": tasks,
        "context": context_section,
        "design_plan": design_plan,
        "design_plan_file": str(plan_file),
        "validation_report": validation_report,
        "validation_report_file": str(report_file),
        "instructions": instructions,
    }


def _extract_tasks(content: str) -> list[dict]:
    """Extract tasks from story markdown."""
    import re

    tasks = []
    pattern = r'^(\s*)-\s*\[([ xX])\]\s*(.+)$'

    for match in re.finditer(pattern, content, re.MULTILINE):
        indent = len(match.group(1))
        completed = match.group(2).lower() == 'x'
        description = match.group(3).strip()

        tasks.append({
            "description": description,
            "completed": completed,
            "indent": indent,
            "is_subtask": indent > 0,
        })

    return tasks


def _build_execution_instructions(
    story_key: str,
    project: ProjectPaths,
    design_plan: str,
    validation_report: str,
    context: str = "",
) -> str:
    """Build execution instructions with plan as primary context."""
    return f"""## Execution Instructions

1. Read the Design Plan below and follow it strictly
2. Implement ALL tasks and subtasks in the story file
3. Do not deviate from the plan without documenting justification in the plan file
4. Update the story file as you complete tasks:
   - Change `- [ ]` to `- [x]`
5. Run tests to verify acceptance criteria
6. When all tasks are complete, update the story status:
   - Use bmad_update_status("{story_key}", "review")

## Design Plan (Primary Context)

{design_plan}

## Validation Report

{validation_report}

{context}

## Project Context

- Project root: {project.root}
- Sprint status: {project.sprint_status}

## Tips

- Follow existing code patterns in the project
- Write tests for new functionality
"""

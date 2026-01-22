"""Execution phase - provide implementation instructions from a validated plan.

Returns lean responses with file paths only. Claude Code reads files directly.
"""

from ..planning import get_story_artifact_dir
from ..planning.validator import validation_passed
from ..project import ProjectPaths


def get_execution_instructions(project: ProjectPaths, story_key: str) -> dict:
    """Get execution instructions for a story based on its design plan.

    Returns file paths and task metadata only - no embedded file content.
    Claude Code should read the referenced files directly.
    """
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

    # Validate plan passed - read just enough to check
    validation_report = report_file.read_text()
    if not validation_passed(validation_report):
        raise ValueError("Design plan validation failed; fix plan before execution.")

    # Extract tasks from story (small, actionable data)
    story_content = story_file.read_text()
    tasks = _extract_tasks(story_content)

    instructions = _build_lean_instructions(story_key)

    return {
        "story_key": story_key,
        "files": {
            "story": str(story_file),
            "design_plan": str(plan_file),
            "validation_report": str(report_file),
        },
        "tasks": tasks,
        "instructions": instructions,
    }


def _extract_tasks(content: str) -> list[dict]:
    """Extract tasks from story markdown (only from ## Tasks section)."""
    import re

    tasks = []

    # Only extract from the ## Tasks section to avoid DoD, manual testing checkboxes
    tasks_match = re.search(r'## Tasks\s*\n(.+?)(?=\n## |\Z)', content, re.DOTALL)
    if not tasks_match:
        return tasks

    tasks_section = tasks_match.group(1)
    pattern = r'^(\s*)-\s*\[([ xX])\]\s*(.+)$'

    for match in re.finditer(pattern, tasks_section, re.MULTILINE):
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


def _build_lean_instructions(story_key: str) -> str:
    """Build lean execution instructions - workflow guidance only, no embedded content."""
    return f"""## How to Implement This Story

**First**: Read the files listed in `files` above:
1. `files.design_plan` - Your implementation blueprint (what to build and how)
2. `files.story` - Requirements and acceptance criteria
3. `files.validation_report` - Confirms the plan is valid

**Then**: For EACH task, follow TDD strictly:

### RED Phase
1. Write a failing test for the expected behavior
2. Run tests - confirm they FAIL
3. If tests pass, your test is wrong

### GREEN Phase
1. Write MINIMUM code to pass the test
2. Run tests - confirm they PASS

### REFACTOR Phase
1. Improve code while keeping tests green
2. Apply patterns from the design plan

### Task Completion
- Update story file: `- [ ]` → `- [x]`
- Add new files to File List section

### When Done
1. `mcp__bmad__bmad_verify_implementation({{story_key: "{story_key}", run_tests: true}})`
2. If verification passes: `mcp__bmad__bmad_review_story({{story_key: "{story_key}"}})`

## Key Rules
- Never skip TDD
- Never mark incomplete tasks complete
- Follow the design plan strictly
"""

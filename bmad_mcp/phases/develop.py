"""Development phase - returns implementation instructions for Claude to execute."""

from pathlib import Path

from ..project import ProjectPaths
from ..context import ContextRetriever


def get_development_instructions(project: ProjectPaths, story_key: str) -> dict:
    """Get development instructions for a story.

    Instead of shelling to aider/claude, this returns the story content
    with structured instructions for the calling Claude to implement directly.
    Includes relevant code context from existing implementation.

    Args:
        project: Project paths
        story_key: Story key (e.g., "0-1-homepage")

    Returns:
        Dictionary with story content and implementation guidance
    """
    story_file = project.stories_dir / f"{story_key}.md"

    if not story_file.exists():
        raise FileNotFoundError(f"Story file not found: {story_file}")

    story_content = story_file.read_text()

    # Parse tasks from story (look for checkboxes)
    tasks = _extract_tasks(story_content)

    # Retrieve context
    retriever = ContextRetriever(project.root)
    context_section = ""
    try:
        context_section = retriever.retrieve_formatted(story_content)
    except Exception as e:
        # Don't fail dev phase if context retrieval fails
        context_section = f"<!-- Context retrieval failed: {e} -->"

    return {
        "story_key": story_key,
        "story_file": str(story_file),
        "story_content": story_content,
        "tasks": tasks,
        "context": context_section,
        "instructions": _build_instructions(story_key, project, context_section),
    }


def _extract_tasks(content: str) -> list[dict]:
    """Extract tasks from story markdown.

    Looks for checkbox items like:
    - [ ] Task description
    - [x] Completed task
    """
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


def _build_instructions(story_key: str, project: ProjectPaths, context: str = "") -> str:
    """Build implementation instructions."""
    return f"""## Implementation Instructions

1. Read the story content above carefully
2. Implement ALL tasks and subtasks in order
3. After completing each task, update the story file to check it off:
   - Change `- [ ]` to `- [x]`
4. Run tests to verify acceptance criteria
5. When all tasks are complete, update the story status:
   - Use bmad_update_status("{story_key}", "review")

{context}

## Project Context

- Project root: {project.root}
- Sprint status: {project.sprint_status}

## Tips

- Follow existing code patterns in the project (see Reference Implementation above)
- Write tests for new functionality
- Commit logical chunks of work
"""

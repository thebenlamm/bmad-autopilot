"""Story creation phase - generates story files from epics."""

from pathlib import Path

from ..llm import call_llm, get_model, DEFAULT_CLAUDE_MODEL
from ..project import ProjectPaths


SYSTEM_PROMPT = """You are a BMAD Story Creator. Your job is to create comprehensive developer implementation guides.

Given the sprint status and epics file, create a complete story file for the specified story key.

The story file MUST include:
1. Story header with title and status (ready-for-dev)
2. User story (As a... I want... So that...)
3. Acceptance Criteria in BDD format (Given/When/Then)
4. Detailed Tasks with checkboxes broken into subtasks
5. Technical requirements and file structure
6. Testing requirements

Output ONLY the markdown content for the story file. No explanations or preamble."""


def build_context(project: ProjectPaths) -> str:
    """Build context string from project files."""
    parts = []

    # Sprint status
    parts.append("=== SPRINT STATUS ===")
    parts.append(project.sprint_status.read_text())
    parts.append("")

    # Epics
    parts.append("=== EPICS ===")
    parts.append(project.epics_file.read_text())
    parts.append("")

    # Architecture (optional)
    if project.architecture_file and project.architecture_file.exists():
        parts.append("=== ARCHITECTURE ===")
        parts.append(project.architecture_file.read_text())
        parts.append("")

    # README for additional context (optional)
    readme = project.root / "README.md"
    if readme.exists():
        parts.append("=== PROJECT README ===")
        parts.append(readme.read_text())
        parts.append("")

    return "\n".join(parts)


def create_story(project: ProjectPaths, story_key: str) -> str:
    """Create a story file from epics.

    Args:
        project: Project paths
        story_key: Story key (e.g., "0-1-homepage")

    Returns:
        Generated story markdown content
    """
    context = build_context(project)
    model = get_model("CLAUDE_MODEL", DEFAULT_CLAUDE_MODEL)

    prompt = f"Create a comprehensive story file for {story_key} based on the context provided."

    response = call_llm(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT,
        model=model,
        context=context,
    )

    return response


def save_story(project: ProjectPaths, story_key: str, content: str) -> Path:
    """Save story content to file.

    Args:
        project: Project paths
        story_key: Story key
        content: Story markdown content

    Returns:
        Path to saved story file
    """
    story_file = project.stories_dir / f"{story_key}.md"

    # Backup existing file if present
    if story_file.exists():
        import time
        backup = story_file.with_suffix(f".md.bak.{int(time.time())}")
        story_file.rename(backup)

    story_file.write_text(content)
    return story_file

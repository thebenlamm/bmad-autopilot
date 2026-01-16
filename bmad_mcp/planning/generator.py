"""Design plan generator using LLM guidance."""

from pathlib import Path

from ..context import ContextRetriever
from ..llm import call_llm, get_model, DEFAULT_CLAUDE_MODEL
from ..project import ProjectPaths
from . import get_story_artifact_dir


SYSTEM_PROMPT = """You are a BMAD Design Planner.

Generate a concrete implementation design plan based on the story, architecture, and code context.
Use the provided template as the structure.

Output ONLY the markdown plan. Do not include preamble or commentary."""


def _template_path() -> Path:
    return Path(__file__).resolve().parent / "templates" / "design-plan.md.j2"


def load_template() -> str:
    """Load the design plan template from disk."""
    template_file = _template_path()
    if template_file.exists():
        return template_file.read_text()
    return "# Design Plan: {story_key}\n\n## 1. Objective\n"


def build_context(project: ProjectPaths, story_key: str) -> str:
    """Build LLM context for the design plan."""
    story_file = project.stories_dir / f"{story_key}.md"
    if not story_file.exists():
        raise FileNotFoundError(f"Story file not found: {story_file}")

    story_content = story_file.read_text()

    parts = [
        "=== STORY ===",
        story_content,
        "",
        "=== SPRINT STATUS ===",
        project.sprint_status.read_text(),
        "",
        "=== EPICS ===",
        project.epics_file.read_text(),
        "",
    ]

    if project.architecture_file and project.architecture_file.exists():
        parts.extend([
            "=== ARCHITECTURE ===",
            project.architecture_file.read_text(),
            "",
        ])

    # Optional code context from the indexer
    retriever = ContextRetriever(project.root)
    try:
        context_section = retriever.retrieve_formatted(story_content)
    except Exception as exc:
        context_section = f"<!-- Context retrieval failed: {exc} -->"

    parts.extend([
        "=== RELEVANT CODE CONTEXT ===",
        context_section,
        "",
    ])

    return "\n".join(parts)


def generate_design_plan(project: ProjectPaths, story_key: str) -> str:
    """Generate a design plan for a story."""
    template = load_template()
    context = build_context(project, story_key)
    model = get_model("CLAUDE_MODEL", DEFAULT_CLAUDE_MODEL)

    prompt = (
        f"Create a detailed design plan for story {story_key}. "
        "Follow the template structure exactly and fill every section with concrete details.\n\n"
        f"TEMPLATE:\n{template.format(story_key=story_key)}"
    )

    response = call_llm(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT,
        model=model,
        context=context,
    )

    if not response.strip():
        raise RuntimeError("LLM returned empty design plan")

    return response


def save_design_plan(project: ProjectPaths, story_key: str, content: str) -> Path:
    """Save the design plan as an artifact."""
    story_dir = get_story_artifact_dir(project, story_key)
    plan_file = story_dir / "design-plan.md"
    plan_file.write_text(content)
    return plan_file

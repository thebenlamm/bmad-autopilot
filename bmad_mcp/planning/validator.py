"""Architecture validator for design plans."""

import re

from ..llm import call_llm, get_model, DEFAULT_REVIEW_MODEL
from ..project import ProjectPaths
from . import get_story_artifact_dir


SYSTEM_PROMPT = """You are an architectural reviewer for BMAD.

Compare the design plan against the provided architecture documentation.
Identify violations, risks, and mismatches.

Return a markdown report with this structure:
## Validation Result
Status: PASS or FAIL

## Risks
- Bullet list of issues (empty list if none)

## Notes
- Additional observations or required follow-ups

Be concise and specific. Output ONLY the markdown report."""


def validate_design_plan(project: ProjectPaths, story_key: str, plan_content: str) -> str:
    """Validate a design plan against architecture documentation."""
    architecture = ""
    if project.architecture_file and project.architecture_file.exists():
        architecture = project.architecture_file.read_text()

    if not architecture.strip():
        return (
            "## Validation Result\n"
            "Status: PASS\n\n"
            "## Risks\n"
            "- None (no architecture constraints found)\n\n"
            "## Notes\n"
            "- Architecture documentation was not found; validation skipped.\n"
        )

    model = get_model("REVIEW_MODEL", DEFAULT_REVIEW_MODEL)
    context = "\n".join([
        "=== ARCHITECTURE ===",
        architecture,
        "",
        "=== DESIGN PLAN ===",
        plan_content,
        "",
    ])

    prompt = f"Validate the design plan for story {story_key} against the architecture."
    response = call_llm(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT,
        model=model,
        context=context,
    )

    if not response.strip():
        raise RuntimeError("LLM returned empty validation report")

    return response


def save_validation_report(project: ProjectPaths, story_key: str, content: str) -> Path:
    """Save validation report as an artifact."""
    story_dir = get_story_artifact_dir(project, story_key)
    report_file = story_dir / "validation-report.md"
    report_file.write_text(content)
    return report_file


def validation_passed(report: str) -> bool:
    """Parse validation report to determine pass/fail."""
    match = re.search(r"^Status:\s*(PASS|FAIL)\b", report, re.IGNORECASE | re.MULTILINE)
    if not match:
        return False
    return match.group(1).upper() == "PASS"

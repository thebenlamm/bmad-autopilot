"""Code review phase - adversarial review using LLM."""

import subprocess
from pathlib import Path

from ..llm import call_llm, get_model, DEFAULT_REVIEW_MODEL
from ..project import ProjectPaths, get_default_branch


SYSTEM_PROMPT = """You are an ADVERSARIAL Senior Developer performing code review.

Your job is to find 3-10 specific issues in the code changes. You MUST find issues - 'looks good' is NOT acceptable.

Review for:
1. Code quality and patterns
2. Test coverage gaps
3. Security issues
4. Performance concerns
5. Acceptance criteria satisfaction

For each issue found:
- Describe the problem specifically
- Reference the file and line
- Suggest the fix
- Rate severity: CRITICAL, HIGH, MEDIUM, LOW

Output a structured review report in markdown format."""


def get_git_diff(project_root: Path, base_branch: str | None = None) -> str:
    """Get git diff from base branch.

    Args:
        project_root: Project root directory
        base_branch: Base branch to compare against (auto-detected if None)

    Returns:
        Git diff output
    """
    if base_branch is None:
        base_branch = get_default_branch(project_root)

    try:
        # Get diff stats
        stats = subprocess.run(
            ["git", "diff", base_branch, "--stat"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )

        # Get full diff
        diff = subprocess.run(
            ["git", "diff", base_branch],
            cwd=project_root,
            capture_output=True,
            text=True,
        )

        if stats.returncode != 0 or diff.returncode != 0:
            return "No diff available (git command failed)"

        return f"{stats.stdout}\n\n{diff.stdout}"

    except Exception as e:
        return f"No diff available: {e}"


def review_story(project: ProjectPaths, story_key: str) -> dict:
    """Run adversarial code review.

    Args:
        project: Project paths
        story_key: Story key being reviewed

    Returns:
        Dictionary with review results
    """
    # Get story content for context
    story_file = project.stories_dir / f"{story_key}.md"
    story_content = ""
    if story_file.exists():
        story_content = story_file.read_text()

    # Get git diff
    diff_content = get_git_diff(project.root)

    # Build context
    context = f"""=== STORY REQUIREMENTS ===
{story_content}

=== CODE CHANGES ===
{diff_content}"""

    # Call LLM for review
    model = get_model("REVIEW_MODEL", DEFAULT_REVIEW_MODEL)

    review = call_llm(
        prompt=f"Perform adversarial code review for story: {story_key}",
        system_prompt=SYSTEM_PROMPT,
        model=model,
        context=context,
    )

    # Check for critical issues
    has_critical = "CRITICAL" in review.upper()

    return {
        "story_key": story_key,
        "review": review,
        "has_critical_issues": has_critical,
        "recommendation": "in-progress" if has_critical else "done",
    }


def save_review(project: ProjectPaths, story_key: str, review_content: str) -> Path:
    """Save review to file.

    Args:
        project: Project paths
        story_key: Story key
        review_content: Review markdown content

    Returns:
        Path to saved review file
    """
    reviews_dir = project.stories_dir / "reviews"
    reviews_dir.mkdir(exist_ok=True)

    review_file = reviews_dir / f"{story_key}-review.md"
    review_file.write_text(review_content)

    return review_file

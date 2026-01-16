"""Planning helpers for design plan generation and validation."""

from pathlib import Path

from ..project import ProjectPaths


def get_story_artifact_dir(project: ProjectPaths, story_key: str) -> Path:
    """Return the per-story artifact directory, creating it if needed."""
    story_dir = project.stories_dir / story_key
    story_dir.mkdir(parents=True, exist_ok=True)
    return story_dir


__all__ = ["get_story_artifact_dir"]

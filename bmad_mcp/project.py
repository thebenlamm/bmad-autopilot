"""Project context management for BMAD MCP server."""

import os
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ProjectPaths:
    """Resolved paths for a BMAD project."""
    root: Path
    sprint_status: Path
    stories_dir: Path
    epics_file: Path
    architecture_file: Path | None = None


class ProjectContext:
    """Manages the active BMAD project context."""

    def __init__(self):
        self._project: ProjectPaths | None = None

    @property
    def project(self) -> ProjectPaths | None:
        return self._project

    @property
    def is_set(self) -> bool:
        return self._project is not None

    def set_project(self, project_path: str) -> ProjectPaths:
        """Validate and set the active project.

        Args:
            project_path: Path to project root directory

        Returns:
            ProjectPaths with resolved paths

        Raises:
            ValueError: If project structure is invalid
        """
        root = Path(project_path).expanduser().resolve()

        if not root.is_dir():
            raise ValueError(f"Project root does not exist: {root}")

        # Find sprint-status.yaml
        sprint_status = None
        stories_dir = None

        for candidate in [
            root / "docs" / "sprint-artifacts" / "sprint-status.yaml",
            root / "sprint-status.yaml",
        ]:
            if candidate.exists():
                sprint_status = candidate
                stories_dir = candidate.parent
                break

        if not sprint_status:
            raise ValueError(
                f"Cannot find sprint-status.yaml in project. "
                f"Expected at docs/sprint-artifacts/ or project root."
            )

        # Find epics.md
        epics_file = None
        for candidate in [
            root / "docs" / "epics.md",
            root / "epics.md",
        ]:
            if candidate.exists():
                epics_file = candidate
                break

        if not epics_file:
            raise ValueError(f"Cannot find epics.md in project.")

        # Find architecture file (optional)
        architecture_file = None
        for candidate in [
            root / "ARCHITECTURE_REALITY.md",
            root / "ARCHITECTURE.md",
            root / "docs" / "architecture.md",
        ]:
            if candidate.exists():
                architecture_file = candidate
                break

        self._project = ProjectPaths(
            root=root,
            sprint_status=sprint_status,
            stories_dir=stories_dir,
            epics_file=epics_file,
            architecture_file=architecture_file,
        )

        return self._project

    def require_project(self) -> ProjectPaths:
        """Get current project, raising if not set."""
        if not self._project:
            raise ValueError(
                "No project set. Use bmad_set_project first."
            )
        return self._project

    def clear(self):
        """Clear the current project context."""
        self._project = None


def validate_story_key(key: str) -> bool:
    """Validate story key format (N-N-slug)."""
    return bool(re.match(r'^[0-9]+-[0-9]+-[a-zA-Z0-9-]+$', key))


def get_default_branch(project_root: Path) -> str:
    """Get the default git branch name."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip().replace("refs/remotes/origin/", "")
    except Exception:
        pass
    return "main"

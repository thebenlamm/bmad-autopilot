"""Safety guards for auto-fix operations."""

import subprocess
from pathlib import Path


class SafetyGuard:
    """Enforces safety rules before applying fixes."""

    def __init__(self, project_root: Path):
        self.project_root = project_root

    def check_git_status(self) -> bool:
        """Check if git working directory is clean.

        Returns:
            True if clean, False otherwise
        """
        try:
            # Check for all changes including untracked files (-u)
            result = subprocess.run(
                ["git", "status", "--porcelain", "-u"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=5
            )
            return len(result.stdout.strip()) == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            # If not a git repo, safety check fails (fail safe)
            return False

    def validate_file_size(self, file_path: Path, max_kb: int = 500) -> bool:
        """Check if file is too large to safely modify.

        Args:
            file_path: Path to file
            max_kb: Maximum size in KB

        Returns:
            True if safe size
        """
        if not file_path.exists():
            return True
        
        size_kb = file_path.stat().st_size / 1024
        return size_kb <= max_kb

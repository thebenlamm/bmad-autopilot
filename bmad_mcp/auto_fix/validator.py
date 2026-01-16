"""Validation orchestrator for auto-fix."""

import subprocess
import tempfile
from pathlib import Path
from typing import Optional


class ValidationOrchestrator:
    """Runs tests to validate fixes."""

    def __init__(self, project_root: Path, timeout: int = 60):
        self.project_root = project_root
        self.timeout = timeout

    def run_tests(self, file_path: Optional[str] = None) -> bool:
        """Run project tests.

        Args:
            file_path: Optional specific file to test (incremental testing)

        Returns:
            True if tests passed
        """
        # Detect test runner
        if (self.project_root / "package.json").exists():
            return self._run_npm_test()
        else:
            return self._run_pytest(file_path)

    def _run_pytest(self, file_path: Optional[str]) -> bool:
        """Run pytest."""
        cmd = ["pytest", "-q"]
        if file_path:
            cmd.append(file_path)
            
        try:
            # Use temp files to avoid buffer issues
            with tempfile.TemporaryFile(mode='w+') as out_f:
                proc = subprocess.run(
                    cmd,
                    cwd=self.project_root,
                    stdout=out_f,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=self.timeout
                )
                return proc.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _run_npm_test(self) -> bool:
        """Run npm test."""
        try:
            with tempfile.TemporaryFile(mode='w+') as out_f:
                proc = subprocess.run(
                    ["npm", "test"],
                    cwd=self.project_root,
                    stdout=out_f,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=self.timeout
                )
                return proc.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

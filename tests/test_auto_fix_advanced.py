"""Advanced tests for auto-fix components (Safety, Modifier, Reporting)."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from bmad_mcp.auto_fix.models import Issue, FixResult, AutoFixReport
from bmad_mcp.auto_fix.modifier import CodeModifier, BackupManager, BackupNotFoundError
from bmad_mcp.auto_fix.safety import SafetyGuard
from bmad_mcp.auto_fix.reporter import ReportGenerator
from bmad_mcp.auto_fix.validator import ValidationOrchestrator


class TestBackupManager:
    """Tests for file backups."""

    def test_backup_and_restore(self, tmp_path):
        """Can backup and restore a file."""
        manager = BackupManager(project_root=tmp_path)
        
        # Create file
        f = tmp_path / "test.txt"
        f.write_text("v1")
        
        # Backup
        backup_path = manager.create_backup(f)
        assert backup_path.exists()
        assert backup_path.name.startswith("test.txt_")
        
        # Modify
        f.write_text("v2")
        
        # Restore
        success = manager.restore_backup(f)
        assert success
        assert f.read_text() == "v1"

    def test_restore_nonexistent_fails(self, tmp_path):
        """Restoring without backup raises BackupNotFoundError."""
        manager = BackupManager(project_root=tmp_path)
        f = tmp_path / "test.txt"
        with pytest.raises(BackupNotFoundError):
            manager.restore_backup(f)


class TestCodeModifier:
    """Tests for safe code modification."""

    def test_write_creates_backup(self, tmp_path):
        """Writing file creates backup first."""
        modifier = CodeModifier(project_root=tmp_path)
        f = tmp_path / "code.py"
        f.write_text("original")
        
        modifier.write_file(f, "modified")
        
        assert f.read_text() == "modified"
        assert modifier.backup_manager.active_backups.get(str(f)) is not None

    def test_rollback(self, tmp_path):
        """Rollback restores previous content."""
        modifier = CodeModifier(project_root=tmp_path)
        f = tmp_path / "code.py"
        f.write_text("original")
        
        modifier.write_file(f, "modified")
        modifier.rollback(f)
        
        assert f.read_text() == "original"


class TestSafetyGuard:
    """Tests for safety checks."""

    def test_file_size_limit(self, tmp_path):
        """Rejects large files."""
        guard = SafetyGuard(project_root=tmp_path)
        f = tmp_path / "large.bin"
        
        # Create 1MB file
        f.write_bytes(b"0" * 1024 * 1024)
        
        assert not guard.validate_file_size(f, max_kb=500)
        assert guard.validate_file_size(f, max_kb=2000)


class TestReportGenerator:
    """Tests for markdown generation."""

    def test_generate_report(self):
        """Generates valid markdown report."""
        issue = Issue(
            severity="HIGH",
            problem="Bad formatting",
            file="src/bad.py",
            fix_type="auto"
        )
        result = FixResult(
            issue=issue,
            status="success",
            changes=["Formatted file"]
        )
        report = AutoFixReport(
            story_key="1-1-test",
            results=[result]
        )
        
        generator = ReportGenerator()
        md = generator.generate_report(report)
        
        assert "# Auto-Fix Report: 1-1-test" in md
        assert "**Fixed:** 1" in md
        assert "✅ SUCCESS: Bad formatting" in md
        assert "- Formatted file" in md


class TestValidationOrchestrator:
    """Tests for test runner wrapper."""

    @patch("subprocess.run")
    def test_run_pytest(self, mock_run, tmp_path):
        """Runs pytest correctly."""
        validator = ValidationOrchestrator(project_root=tmp_path)
        
        # Mock success
        mock_run.return_value = MagicMock(returncode=0)
        
        assert validator.run_tests()
        mock_run.assert_called()
        args = mock_run.call_args[0][0]
        assert "pytest" in args

"""Code modification system with safety and rollback capabilities."""

import shutil
import time
import uuid
import os
import tempfile
from pathlib import Path
from typing import Optional


class BackupNotFoundError(Exception):
    """Raised when a backup cannot be found for restoration."""
    pass


class BackupManager:
    """Manages file backups and rollbacks."""

    def __init__(self, project_root: Path, backup_dir: str = ".bmad/backups"):
        self.project_root = project_root.resolve()
        self.backup_dir = self.project_root / backup_dir
        self.active_backups: dict[str, Path] = {}

    def create_backup(self, file_path: Path) -> Path:
        """Create a backup of a file with a unique name to prevent collisions."""
        if not file_path.exists():
            raise FileNotFoundError(f"Cannot backup non-existent file: {file_path}")

        # Ensure backup dir exists
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Create unique backup name using timestamp and UUID fragment (CRITICAL-2)
        timestamp = int(time.time() * 1000)
        u_id = uuid.uuid4().hex[:8]
        rel_path = file_path.resolve().relative_to(self.project_root).as_posix().replace("/", "_")
        backup_name = f"{rel_path}_{timestamp}_{u_id}.bak"
        backup_path = self.backup_dir / backup_name

        shutil.copy2(file_path, backup_path)
        self.active_backups[str(file_path.resolve())] = backup_path
        
        return backup_path

    def restore_backup(self, file_path: Path) -> bool:
        """Restore a file from its active backup. Raises if no backup found."""
        backup_path = self.active_backups.get(str(file_path.resolve()))
        if not backup_path or not backup_path.exists():
            raise BackupNotFoundError(f"No active backup found for: {file_path}")

        # Use atomic write logic for restoration as well
        with open(backup_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Use CodeModifier's atomic write logic if possible, 
        # but here we just do a safe copy
        shutil.copy2(backup_path, file_path)
        return True

    def clear_backup(self, file_path: Path) -> None:
        """Clear active backup record for a file (without deleting file)."""
        abs_path = str(file_path.resolve())
        if abs_path in self.active_backups:
            del self.active_backups[abs_path]

    def cleanup_old_backups(self, max_age_seconds: int = 86400):
        """Delete backups older than max_age, preserving active ones (HIGH-6)."""
        if not self.backup_dir.exists():
            return

        active_paths = {str(p.resolve()) for p in self.active_backups.values()}
        now = time.time()
        for backup in self.backup_dir.glob("*.bak"):
            if str(backup.resolve()) in active_paths:
                continue
                
            if now - backup.stat().st_mtime > max_age_seconds:
                try:
                    backup.unlink()
                except OSError:
                    pass


class CodeModifier:
    """Safely modifies code files with atomic writes and path validation."""

    def __init__(self, project_root: Path, backup_manager: Optional[BackupManager] = None):
        self.project_root = project_root.resolve()
        self.backup_manager = backup_manager or BackupManager(self.project_root)

    def validate_path(self, file_path: Path) -> Path:
        """Ensure path is within project root to prevent traversal (CRITICAL-1)."""
        resolved = file_path.resolve()
        try:
            resolved.relative_to(self.project_root)
            return resolved
        except ValueError:
            raise PermissionError(f"Access denied: {file_path} is outside project root")

    def write_file(self, file_path: Path, content: str) -> None:
        """Write content to file atomically with backup (HIGH-5)."""
        target_path = self.validate_path(file_path)
        
        # Create backup first
        if target_path.exists():
            self.backup_manager.create_backup(target_path)
        
        # Atomic write: temp file + rename
        # This prevents file corruption if the process is killed during write
        fd, temp_path = tempfile.mkstemp(
            dir=target_path.parent, 
            prefix=f".{target_path.name}", 
            suffix=".tmp"
        )
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno()) # Ensure data is on disk
            
            # Atomic rename (on POSIX)
            os.replace(temp_path, target_path)
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    def rollback(self, file_path: Path) -> bool:
        """Rollback file to previous state."""
        return self.backup_manager.restore_backup(self.validate_path(file_path))

"""Sprint status YAML operations."""

import os
import sys
import tempfile
import fcntl
import contextlib
from pathlib import Path
from typing import Literal

import yaml


Status = Literal["backlog", "ready-for-dev", "in-progress", "review", "done", "blocked"]

VALID_STATUSES = {"backlog", "ready-for-dev", "in-progress", "review", "done", "blocked"}


@contextlib.contextmanager
def _sprint_lock(path: Path):
    """File lock context manager to prevent race conditions."""
    lock_path = path.parent / ".sprint-status.lock"
    with open(lock_path, 'a') as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def load_sprint_status(path: Path) -> dict:
    """Load sprint-status.yaml."""
    try:
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


def save_sprint_status(path: Path, data: dict):
    """Save sprint-status.yaml atomically.

    Uses temp file + rename pattern to prevent race conditions when
    multiple processes write to the same file concurrently.
    """
    dir_path = path.parent

    # Write to temp file in same directory (required for atomic rename)
    fd, temp_path = tempfile.mkstemp(suffix='.tmp', dir=dir_path)
    try:
        with os.fdopen(fd, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        # Atomic rename (replace handles existing files on Windows too)
        os.replace(temp_path, path)
    except Exception:
        # Clean up temp file on failure
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise


def get_development_status(path: Path) -> dict[str, str]:
    """Get development_status section."""
    data = load_sprint_status(path)
    return data.get("development_status", {})


def get_stories_by_status(path: Path, status: Status) -> list[str]:
    """Get list of story keys with given status."""
    dev_status = get_development_status(path)
    return [
        key for key, value in dev_status.items()
        if value == status and _is_story_key(key)
    ]


def get_next_story(path: Path, status: Status) -> str | None:
    """Get the next story with given status."""
    stories = get_stories_by_status(path, status)
    return stories[0] if stories else None


def get_stories_for_epic(path: Path, epic_num: int) -> dict[str, str]:
    """Get all stories for an epic with their statuses."""
    prefix = f"{epic_num}-"
    dev_status = get_development_status(path)
    return {
        key: value for key, value in dev_status.items()
        if key.startswith(prefix) and _is_story_key(key)
    }


def update_story_status(path: Path, story_key: str, new_status: Status) -> bool:
    """Update a story's status.

    Returns:
        True if updated successfully
    """
    if new_status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {new_status}")

    # Use lock to prevent lost updates during read-modify-write cycle
    with _sprint_lock(path):
        data = load_sprint_status(path)
        if "development_status" not in data:
            data["development_status"] = {}

        data["development_status"][story_key] = new_status
        save_sprint_status(path, data)

    # Verify
    actual = get_development_status(path).get(story_key)
    return actual == new_status


def get_status_summary(path: Path) -> dict[str, int]:
    """Get count of stories by status."""
    dev_status = get_development_status(path)
    counts: dict[str, int] = {}

    for key, status in dev_status.items():
        if _is_story_key(key):
            counts[status] = counts.get(status, 0) + 1

    return counts


def _is_story_key(key: str) -> bool:
    """Check if key looks like a story key (N-N-...)."""
    parts = key.split("-")
    return len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit()

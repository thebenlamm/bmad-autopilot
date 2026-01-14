"""Tests for sprint status functionality."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from bmad_mcp.sprint import (
    load_sprint_status,
    save_sprint_status,
    update_story_status,
    get_stories_by_status,
    get_status_summary,
    _is_story_key,
    VALID_STATUSES,
)


@pytest.fixture
def temp_sprint_file():
    """Create a temporary sprint-status.yaml file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump({
            "development_status": {
                "0-1-homepage": "backlog",
                "0-2-navigation": "ready-for-dev",
                "1-1-auth": "in-progress",
            }
        }, f)
        path = Path(f.name)
    yield path
    # Cleanup
    if path.exists():
        path.unlink()


class TestAtomicWrites:
    """Test atomic write functionality."""

    def test_save_creates_file(self, temp_sprint_file):
        """Save creates/updates file correctly."""
        data = {"development_status": {"0-1-test": "done"}}
        save_sprint_status(temp_sprint_file, data)

        loaded = load_sprint_status(temp_sprint_file)
        assert loaded == data

    def test_save_is_atomic(self, temp_sprint_file):
        """Save uses atomic write (no partial writes)."""
        # Write initial data
        initial = {"development_status": {"0-1-test": "backlog"}}
        save_sprint_status(temp_sprint_file, initial)

        # Write new data
        new_data = {"development_status": {"0-1-test": "done", "0-2-new": "backlog"}}
        save_sprint_status(temp_sprint_file, new_data)

        # Verify complete write
        loaded = load_sprint_status(temp_sprint_file)
        assert loaded == new_data

    def test_no_temp_files_left(self, temp_sprint_file):
        """No temporary files left after save."""
        parent_dir = temp_sprint_file.parent
        initial_files = set(os.listdir(parent_dir))

        save_sprint_status(temp_sprint_file, {"development_status": {}})

        final_files = set(os.listdir(parent_dir))
        new_files = final_files - initial_files
        temp_files = [f for f in new_files if f.endswith('.tmp')]
        assert len(temp_files) == 0


class TestUpdateStoryStatus:
    """Test story status updates."""

    def test_update_existing_story(self, temp_sprint_file):
        """Update status of existing story."""
        result = update_story_status(temp_sprint_file, "0-1-homepage", "ready-for-dev")
        assert result is True

        loaded = load_sprint_status(temp_sprint_file)
        assert loaded["development_status"]["0-1-homepage"] == "ready-for-dev"

    def test_add_new_story(self, temp_sprint_file):
        """Add new story with status."""
        result = update_story_status(temp_sprint_file, "2-1-new-feature", "backlog")
        assert result is True

        loaded = load_sprint_status(temp_sprint_file)
        assert loaded["development_status"]["2-1-new-feature"] == "backlog"

    def test_invalid_status_raises(self, temp_sprint_file):
        """Invalid status raises ValueError."""
        with pytest.raises(ValueError, match="Invalid status"):
            update_story_status(temp_sprint_file, "0-1-homepage", "invalid-status")


class TestStoryKeyValidation:
    """Test story key format validation."""

    def test_valid_story_keys(self):
        """Valid story key formats."""
        assert _is_story_key("0-1-homepage") is True
        assert _is_story_key("1-2-auth-login") is True
        assert _is_story_key("10-20-long-slug-name") is True

    def test_invalid_story_keys(self):
        """Invalid story key formats."""
        assert _is_story_key("homepage") is False
        assert _is_story_key("0-homepage") is False
        assert _is_story_key("a-1-homepage") is False
        assert _is_story_key("0-a-homepage") is False


class TestGetStoriesByStatus:
    """Test filtering stories by status."""

    def test_get_backlog_stories(self, temp_sprint_file):
        """Get stories in backlog status."""
        stories = get_stories_by_status(temp_sprint_file, "backlog")
        assert "0-1-homepage" in stories
        assert len(stories) == 1

    def test_get_empty_status(self, temp_sprint_file):
        """Get empty list for status with no stories."""
        stories = get_stories_by_status(temp_sprint_file, "done")
        assert stories == []


class TestGetStatusSummary:
    """Test status summary counts."""

    def test_summary_counts(self, temp_sprint_file):
        """Get correct counts by status."""
        summary = get_status_summary(temp_sprint_file)
        assert summary.get("backlog") == 1
        assert summary.get("ready-for-dev") == 1
        assert summary.get("in-progress") == 1

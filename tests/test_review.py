"""Tests for review phase functionality."""

from unittest.mock import patch

import pytest
from bmad_mcp.phases.review import review_story, validate_branch_name
from bmad_mcp.project import ProjectPaths


class TestValidateBranchName:
    """Test branch name validation for security."""

    def test_valid_simple_branches(self):
        """Valid simple branch names."""
        assert validate_branch_name("main") is True
        assert validate_branch_name("master") is True
        assert validate_branch_name("develop") is True

    def test_valid_feature_branches(self):
        """Valid feature branch patterns."""
        assert validate_branch_name("feature/my-feature") is True
        assert validate_branch_name("bugfix/fix-123") is True
        assert validate_branch_name("release/v1.0.0") is True

    def test_valid_with_special_chars(self):
        """Valid branches with allowed special characters."""
        assert validate_branch_name("feature_branch") is True
        assert validate_branch_name("branch.name") is True
        assert validate_branch_name("user/branch-name") is True
        assert validate_branch_name("origin/HEAD") is True

    def test_reject_flag_injection(self):
        """Reject branch names that look like git flags."""
        assert validate_branch_name("-v") is False
        assert validate_branch_name("--version") is False
        assert validate_branch_name("-h") is False
        assert validate_branch_name("--help") is False
        assert validate_branch_name("--exec=whoami") is False

    def test_reject_empty(self):
        """Reject empty branch names."""
        assert validate_branch_name("") is False

    def test_reject_shell_metacharacters(self):
        """Reject shell metacharacters that could enable injection."""
        assert validate_branch_name("branch; rm -rf /") is False
        assert validate_branch_name("branch && whoami") is False
        assert validate_branch_name("branch | cat /etc/passwd") is False
        assert validate_branch_name("$(whoami)") is False
        assert validate_branch_name("`whoami`") is False
        assert validate_branch_name("branch\nrm -rf /") is False

    def test_reject_spaces(self):
        """Reject branch names with spaces."""
        assert validate_branch_name("branch name") is False
        assert validate_branch_name(" branch") is False
        assert validate_branch_name("branch ") is False


class TestReviewStory:
    """Test review story failure handling."""

    def test_review_story_fails_closed_on_diff_error(self, tmp_path):
        """Review should fail closed if git diff generation fails."""
        project = ProjectPaths(
            root=tmp_path,
            sprint_status=tmp_path / "sprint-status.yaml",
            stories_dir=tmp_path,
            epics_file=tmp_path / "epics.md",
        )

        with patch("bmad_mcp.phases.review.get_git_diff", side_effect=RuntimeError("git diff failed")):
            result = review_story(project, "0-1-homepage")

        assert result["has_critical_issues"] is True
        assert result["recommendation"] == "in-progress"
        assert "Review failed" in result["review"]
        assert result["structured_issues"][0]["severity"] == "CRITICAL"

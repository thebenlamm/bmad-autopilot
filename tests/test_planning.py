"""Tests for planning and execution phases."""

from pathlib import Path

import pytest

from bmad_mcp.phases.execute import get_execution_instructions
from bmad_mcp.phases.plan import plan_implementation
from bmad_mcp.planning.validator import validation_passed
from bmad_mcp.project import ProjectContext


def _build_project(tmp_path: Path) -> tuple[ProjectContext, str]:
    story_key = "1-1-test-story"
    docs_dir = tmp_path / "docs"
    sprint_dir = docs_dir / "sprint-artifacts"
    sprint_dir.mkdir(parents=True)

    (sprint_dir / "sprint-status.yaml").write_text("development_status: {}\n")
    (docs_dir / "epics.md").write_text("# Epics\n")
    (tmp_path / "ARCHITECTURE.md").write_text("Architecture rules.\n")

    story_file = sprint_dir / f"{story_key}.md"
    story_file.write_text(
        "# Test Story\n\n"
        "## Tasks\n"
        "- [ ] Do the thing\n"
        "  - [ ] Subtask\n"
    )

    ctx = ProjectContext()
    ctx.set_project(str(tmp_path))
    return ctx, story_key


def test_plan_implementation_creates_artifacts(tmp_path, monkeypatch):
    ctx, story_key = _build_project(tmp_path)

    monkeypatch.setattr(
        "bmad_mcp.planning.generator.call_llm",
        lambda **kwargs: "# Design Plan\n\nPlan content\n",
    )
    monkeypatch.setattr(
        "bmad_mcp.planning.validator.call_llm",
        lambda **kwargs: (
            "## Validation Result\n"
            "Status: PASS\n\n"
            "## Risks\n"
            "- None\n\n"
            "## Notes\n"
            "- OK\n"
        ),
    )

    data = plan_implementation(ctx.project, story_key)
    assert data["validation_passed"] is True
    assert Path(data["design_plan_file"]).exists()
    assert Path(data["validation_report_file"]).exists()


def test_execute_instructions_require_validated_plan(tmp_path):
    ctx, story_key = _build_project(tmp_path)

    story_dir = ctx.project.stories_dir / story_key
    story_dir.mkdir(parents=True, exist_ok=True)
    (story_dir / "design-plan.md").write_text("# Design Plan\n\nPlan content\n")
    (story_dir / "validation-report.md").write_text(
        "## Validation Result\nStatus: PASS\n\n## Risks\n- None\n"
    )

    data = get_execution_instructions(ctx.project, story_key)
    assert "Design Plan" in data["instructions"]
    assert data["design_plan"]
    assert data["validation_report"]


def test_validation_passed_parses_status():
    assert validation_passed("Status: PASS") is True
    assert validation_passed("Status: FAIL") is False

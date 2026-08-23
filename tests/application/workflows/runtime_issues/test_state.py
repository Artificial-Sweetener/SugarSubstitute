#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Tests for workflow cube runtime issue state."""

from __future__ import annotations

from substitute.application.workflows import (
    CubeRuntimeIssue,
    CubeRuntimeIssueKind,
    CubeRuntimeIssueSeverity,
    CubeRuntimeIssueSource,
    WorkflowIssueState,
)


def _issue(
    *,
    workflow_id: str = "workflow-a",
    cube_alias: str = "Cube",
    source: CubeRuntimeIssueSource = CubeRuntimeIssueSource.PROJECTION,
    severity: CubeRuntimeIssueSeverity = CubeRuntimeIssueSeverity.ERROR,
    kind: CubeRuntimeIssueKind = CubeRuntimeIssueKind.MISSING_LIVE_NODE_DEFINITION,
    message: str = "Missing live node definition.",
) -> CubeRuntimeIssue:
    """Build a deterministic issue for issue-state tests."""

    return CubeRuntimeIssue(
        workflow_id=workflow_id,
        cube_alias=cube_alias,
        severity=severity,
        kind=kind,
        message=message,
        operation="test",
        source=source,
        missing_node_classes=("KSampler",),
        node_names=("sampler",),
        recommended_action="Restart ComfyUI.",
    )


def test_replace_projection_issues_preserves_other_sources() -> None:
    """Projection refresh should replace only projection-owned issues."""

    state = WorkflowIssueState()
    library_issue = _issue(source=CubeRuntimeIssueSource.CUBE_LIBRARY)
    stale_projection_issue = _issue(cube_alias="Old")
    state.add_issues((library_issue, stale_projection_issue))

    state.replace_projection_issues(
        "workflow-a",
        (_issue(cube_alias="New"),),
        CubeRuntimeIssueSource.PROJECTION,
    )

    assert set(state.issues_for_workflow("workflow-a")) == {
        library_issue,
        _issue(cube_alias="New"),
    }


def test_clear_cube_issues_removes_only_target_cube() -> None:
    """Clearing one cube should leave other cube issues intact."""

    state = WorkflowIssueState()
    other_issue = _issue(cube_alias="Other")
    state.add_issues((_issue(cube_alias="Cube"), other_issue))

    state.clear_cube_issues("workflow-a", "Cube")

    assert state.issues_for_workflow("workflow-a") == (other_issue,)


def test_errored_aliases_ignores_warning_issues() -> None:
    """Errored aliases should include only error severity issues."""

    state = WorkflowIssueState()
    state.add_issues(
        (
            _issue(cube_alias="Warn", severity=CubeRuntimeIssueSeverity.WARNING),
            _issue(cube_alias="Error", severity=CubeRuntimeIssueSeverity.ERROR),
        )
    )

    assert state.errored_aliases("workflow-a") == ("Error",)
    assert state.has_error("workflow-a", "Error")
    assert not state.has_error("workflow-a", "Warn")


def test_duplicate_issues_collapse_deterministically() -> None:
    """Adding the same issue twice should keep one deterministic record."""

    state = WorkflowIssueState()
    issue = _issue()
    state.add_issues((issue, issue))

    assert state.issues_for_cube("workflow-a", "Cube") == (issue,)

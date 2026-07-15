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

"""Cover pure workspace append collision policy."""

from __future__ import annotations

from substitute.application.workspace_state.workspace_append_service import (
    WorkspaceAppendService,
)
from substitute.domain.workflow import WorkflowState
from substitute.domain.workspace_snapshot import (
    ShellLayoutSnapshot,
    WorkflowSnapshot,
    WorkspaceSnapshot,
)


def test_snapshot_with_unique_open_ids_remaps_colliding_workflows() -> None:
    """Append restore should avoid open workflow id and tab-label collisions."""

    snapshot = WorkspaceSnapshot(
        schema_version="1",
        workflows=(
            WorkflowSnapshot(
                workflow_id="wf-a",
                tab_label="Untitled Recipe",
                workflow=WorkflowState(),
            ),
        ),
        tab_order=("wf-a",),
        active_route="wf-a",
        shell_layout=ShellLayoutSnapshot(),
    )

    result = WorkspaceAppendService().snapshot_with_unique_open_ids(
        snapshot,
        existing_workflow_ids={"wf-a"},
        existing_tab_labels={"Untitled Workflow", "Untitled Workflow (2)"},
    )

    assert result.workflows[0].workflow_id == "wf-a-2"
    assert result.workflows[0].tab_label == "Untitled Workflow (3)"
    assert result.tab_order == ("wf-a-2",)
    assert result.active_route == "wf-a-2"
    assert result.shell_layout is None


def test_unique_restored_workflow_label_migrates_legacy_defaults() -> None:
    """Legacy generated tab labels should normalize before collision checks."""

    assert (
        WorkspaceAppendService.unique_restored_workflow_label(
            "Untitled Recipe",
            set(),
        )
        == "Untitled Workflow"
    )
    assert (
        WorkspaceAppendService.unique_restored_workflow_label(
            "Untitled Recipe (3)",
            set(),
        )
        == "Untitled Workflow (3)"
    )
    assert (
        WorkspaceAppendService.unique_restored_workflow_label(
            "Untitled Recipe Draft",
            set(),
        )
        == "Untitled Recipe Draft"
    )
    assert (
        WorkspaceAppendService.unique_restored_workflow_label(
            "Untitled Recipe (2)",
            {"Untitled Workflow (2)"},
        )
        == "Untitled Workflow (2) (2)"
    )


def test_unique_restored_workflow_label_uniquifies_after_legacy_migration() -> None:
    """Restore should resolve conflicts after migrating generated legacy labels."""

    assert (
        WorkspaceAppendService.unique_restored_workflow_label(
            "Untitled Recipe",
            {"Untitled Workflow"},
        )
        == "Untitled Workflow (2)"
    )

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

"""Workflow close, snapshot, and cleanup contracts."""

from __future__ import annotations


from substitute.application.workflows import (
    ClosedWorkflowBuffer,
)


from tests.presentation.shell.workflow_surface.workflow_action_fakes import (
    _SnapshotCapture,
    _import_module,
)
from tests.presentation.shell.workflow_surface.workflow_action_support import (
    _build_view,
)


def test_active_workflow_close_projects_successor_without_final_toolbar_clear() -> None:
    """Closing active workflow should project successor once without clearing it after."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-b")

    mod.WorkflowWorkspaceCoordinator(view).close_workflow("wf-b")

    assert "wf-a:clear" not in view.calls
    assert view.workflow_session_service.active_workflow_id == "wf-a"
    assert view.workflow_tabbar.removed == [("wf-b", False)]
    assert view.workflow_tabbar.selected == [("wf-a", False)]
    assert view.calls.count("refresh") == 1
    assert view.calls.count("canvas:project:wf-a") == 1
    assert "progress:remove:wf-b" in view.calls
    assert "progress:project" in view.calls
    assert "input:prune" not in view.calls
    assert "canvas:prune" not in view.calls
    assert "wf-b:dispose" in view.calls
    assert view.closed_workflow_buffer.summaries()[0].workflow_id == "wf-b"
    assert view.reopen_enabled_states[-1] is True


def test_inactive_workflow_close_leaves_active_surfaces_alone() -> None:
    """Closing inactive workflow should not refresh or reproject active workflow."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")

    mod.WorkflowWorkspaceCoordinator(view).close_workflow("wf-b")

    assert view.workflow_session_service.active_workflow_id == "wf-a"
    assert "wf-a:clear" not in view.calls
    assert "refresh" not in view.calls
    assert "canvas:project:wf-a" not in view.calls
    assert view.workflow_tabbar.removed == [("wf-b", False)]
    assert view.closed_workflow_buffer.summaries()[0].workflow_id == "wf-b"
    assert view.reopen_enabled_states[-1] is True


def test_close_workflow_captures_snapshot_through_snapshot_adapter() -> None:
    """Closing a workflow should capture reopen state through the snapshot port."""

    mod = _import_module()
    view = _build_view(active_workflow_id="wf-a")
    view.session_snapshot_capture_adapter = _SnapshotCapture(view.calls)

    mod.WorkflowWorkspaceCoordinator(view).close_workflow("wf-b")

    record = view.closed_workflow_buffer.pop_latest()
    assert record is not None
    snapshot = view.closed_workflow_snapshot_service.decode(record.snapshot_payload)
    assert record.tab_label == "Snapshot wf-b"
    assert snapshot.tab_label == "Snapshot wf-b"
    assert snapshot.active_cube_alias == "SnapshotCube"
    assert "snapshot:label:wf-b" in view.calls
    assert "snapshot:active-cube:wf-b" in view.calls
    assert "snapshot:input-images:wf-b" in view.calls
    assert "snapshot:input-masks:wf-b" in view.calls
    assert "snapshot:output-images:wf-b" in view.calls
    assert "snapshot:viewport:wf-b" in view.calls


def test_close_workflow_cleans_evicted_buffer_records() -> None:
    """Closing workflows should prune older records evicted from the reopen buffer."""

    mod = _import_module()
    view = _build_view(
        active_workflow_id="wf-b",
        closed_workflow_buffer=ClosedWorkflowBuffer(budget_bytes=1400),
    )

    mod.WorkflowWorkspaceCoordinator(view).close_workflow("wf-b")
    mod.WorkflowWorkspaceCoordinator(view).close_workflow("wf-a")

    assert "input:prune" in view.calls
    assert "canvas:prune" in view.calls
    assert [
        summary.workflow_id for summary in view.closed_workflow_buffer.summaries()
    ] == ["wf-a"]


def test_close_workflow_prunes_immediately_when_record_rejected() -> None:
    """Oversized close snapshots should fall back to immediate cleanup."""

    mod = _import_module()
    view = _build_view(closed_workflow_buffer=ClosedWorkflowBuffer(budget_bytes=1))

    mod.WorkflowWorkspaceCoordinator(view).close_workflow("wf-b")

    assert "input:prune" in view.calls
    assert "canvas:prune" in view.calls
    assert view.closed_workflow_buffer.summaries() == ()


class _FailingClosedWorkflowSnapshotService:
    """Snapshot service double that forces close-time capture failure."""

    def encode(self, _snapshot: object) -> bytes:
        """Raise during encoding to exercise close fallback cleanup."""

        raise ValueError("capture failed")


def test_close_workflow_prunes_immediately_when_snapshot_capture_fails() -> None:
    """Snapshot capture failures should not block normal workflow close cleanup."""

    mod = _import_module()
    view = _build_view(
        closed_workflow_snapshot_service=_FailingClosedWorkflowSnapshotService()
    )

    mod.WorkflowWorkspaceCoordinator(view).close_workflow("wf-b")

    assert "input:prune" in view.calls
    assert "canvas:prune" in view.calls
    assert view.closed_workflow_buffer.summaries() == ()

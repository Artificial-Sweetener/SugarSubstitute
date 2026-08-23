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

"""Closed-workflow reopen and rekeying contracts."""

from __future__ import annotations

from datetime import UTC, datetime


from substitute.application.workflows import (
    ClosedWorkflowBuffer,
    ClosedWorkflowRecord,
    ClosedWorkflowSnapshotService,
)
from substitute.domain.workflow import CubeState, WorkflowState
from substitute.domain.workspace_snapshot import (
    WorkflowSnapshot,
)


from tests.presentation.shell.workflow_surface.workflow_action_fakes import (
    _import_module,
)
from tests.presentation.shell.workflow_surface.workflow_action_support import (
    _build_view,
)


def _closed_record(
    *,
    workflow_id: str = "wf-closed",
    tab_label: str = "Closed Workflow",
    tab_index: int = 1,
    payload: bytes | None = None,
    workflow: WorkflowState | None = None,
) -> ClosedWorkflowRecord:
    """Build a closed workflow record for coordinator reopen tests."""

    if payload is None:
        snapshot = WorkflowSnapshot(
            workflow_id=workflow_id,
            tab_label=tab_label,
            workflow=workflow
            or WorkflowState(
                cubes={
                    "Demo": CubeState(
                        cube_id="demo",
                        version="1",
                        alias="Demo",
                        original_cube={},
                        buffer={"value": 1},
                    )
                },
                stack_order=["Demo"],
            ),
            active_cube_alias="Demo",
        )
        payload = ClosedWorkflowSnapshotService().encode(snapshot)
    return ClosedWorkflowRecord(
        close_id=f"close-{workflow_id}",
        workflow_id=workflow_id,
        tab_label=tab_label,
        tab_index=tab_index,
        snapshot_payload=payload,
        payload_size_bytes=len(payload),
        closed_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_reopen_latest_closed_workflow_restores_session_workflow() -> None:
    """Reopening should register and activate the buffered workflow state."""

    mod = _import_module()
    buffer = ClosedWorkflowBuffer()
    buffer.push(_closed_record())
    view = _build_view(closed_workflow_buffer=buffer)

    reopened = mod.WorkflowWorkspaceCoordinator(view).reopen_latest_closed_workflow()

    assert reopened is True
    assert "wf-closed" in view.workflow_session_service.workflows
    assert view.workflow_session_service.active_workflow_id == "wf-closed"
    assert view.workflow_tabbar.itemMap["wf-closed"].text() == "Closed Workflow"
    assert view.reopen_enabled_states[-1] is False


def test_reopen_latest_closed_workflow_uses_preferred_tab_index() -> None:
    """Reopening should insert the tab near its stored close-time index."""

    mod = _import_module()
    buffer = ClosedWorkflowBuffer()
    buffer.push(_closed_record(workflow_id="wf-closed", tab_index=1))
    view = _build_view(closed_workflow_buffer=buffer)

    mod.WorkflowWorkspaceCoordinator(view).reopen_latest_closed_workflow()

    assert view.workflow_tabbar.workflow_ids_in_order() == [
        "wf-a",
        "wf-closed",
        "wf-b",
    ]


def test_reopen_latest_closed_workflow_returns_false_when_empty() -> None:
    """Empty closed workflow buffers should make reopen a no-op."""

    mod = _import_module()
    view = _build_view()

    assert (
        mod.WorkflowWorkspaceCoordinator(view).reopen_latest_closed_workflow() is False
    )
    assert view.workflow_session_service.active_workflow_id == "wf-a"


def test_reopen_latest_closed_workflow_rekeys_on_id_collision() -> None:
    """Reopening should not overwrite an already-open workflow id."""

    mod = _import_module()
    buffer = ClosedWorkflowBuffer()
    buffer.push(_closed_record(workflow_id="wf-b", tab_label="Old B"))
    view = _build_view(closed_workflow_buffer=buffer)

    reopened = mod.WorkflowWorkspaceCoordinator(view).reopen_latest_closed_workflow()

    assert reopened is True
    assert "wf-b" in view.workflow_session_service.workflows
    assert "wf-b_reopened" in view.workflow_session_service.workflows
    assert view.workflow_session_service.active_workflow_id == "wf-b_reopened"
    assert view.workflow_tabbar.itemMap["wf-b_reopened"].text() == "Old B"


def test_reopen_latest_closed_workflow_drops_corrupt_payload_without_crash() -> None:
    """Corrupt buffered payloads should fail gracefully and leave session unchanged."""

    mod = _import_module()
    buffer = ClosedWorkflowBuffer()
    buffer.push(_closed_record(payload=b"not json"))
    view = _build_view(closed_workflow_buffer=buffer)

    reopened = mod.WorkflowWorkspaceCoordinator(view).reopen_latest_closed_workflow()

    assert reopened is False
    assert view.workflow_session_service.active_workflow_id == "wf-a"
    assert buffer.summaries() == ()
    assert view.reopen_enabled_states[-1] is False


def test_reopen_latest_closed_workflow_projects_once() -> None:
    """Reopening should project the restored active workflow once."""

    mod = _import_module()
    buffer = ClosedWorkflowBuffer()
    buffer.push(_closed_record())
    view = _build_view(closed_workflow_buffer=buffer)

    mod.WorkflowWorkspaceCoordinator(view).reopen_latest_closed_workflow()

    assert view.calls.count("canvas:project:wf-closed") == 1

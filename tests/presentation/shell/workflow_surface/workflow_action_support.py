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

"""Compose workflow-action coordinator test state."""

from __future__ import annotations

from types import SimpleNamespace


from substitute.application.workflows import (
    ClosedWorkflowBuffer,
    ClosedWorkflowSnapshotService,
    WorkflowSessionService,
    WorkflowTabService,
)
from substitute.domain.workflow import WorkflowState
from substitute.presentation.shell.workflow_surface_results import WorkflowUiSurfaces


from tests.presentation.shell.workflow_surface.workflow_action_fakes import (
    _Manager,
    _TabBar,
    _deletable,
)


def _build_view(
    *,
    active_workflow_id: str = "wf-a",
    closed_workflow_buffer: ClosedWorkflowBuffer | None = None,
    closed_workflow_snapshot_service: object | None = None,
) -> SimpleNamespace:
    """Build coordinator view double with two workflow states."""

    calls: list[str] = []
    session = WorkflowSessionService(WorkflowState, default_workflow_id="wf-a")
    session.add_workflow("wf-b")
    if active_workflow_id != "wf-a":
        session.activate_workflow(active_workflow_id)

    tabbar = _TabBar(["wf-a", "wf-b"])
    reopen_enabled_states: list[bool] = []

    def refresh_active_workflow_surface(**kwargs: object) -> None:
        """Record refresh and run optional completion callback."""

        calls.append("refresh")
        on_complete = kwargs.get("on_complete")
        if callable(on_complete):
            on_complete()

    def create_new_workflow_ui(
        workflow_id: str,
        set_as_current: bool = True,
    ) -> WorkflowUiSurfaces:
        """Create workflow UI doubles and record the request."""

        calls.append(f"create:{workflow_id}:{set_as_current}")
        return WorkflowUiSurfaces(
            cube_stack=_deletable(f"{workflow_id}:cube", calls),
            editor_panel=_deletable(f"{workflow_id}:editor", calls),
            created=True,
        )

    view = SimpleNamespace(
        calls=calls,
        closed_workflow_buffer=closed_workflow_buffer or ClosedWorkflowBuffer(),
        closed_workflow_snapshot_service=(
            closed_workflow_snapshot_service or ClosedWorkflowSnapshotService()
        ),
        workflow_tab_service=WorkflowTabService(),
        workflow_session_service=session,
        workflow_tabbar=tabbar,
        cube_stacks={
            "wf-a": _deletable("wf-a:cube", calls),
            "wf-b": _deletable("wf-b:cube", calls),
        },
        editor_panels={
            "wf-a": _deletable("wf-a:editor", calls),
            "wf-b": _deletable("wf-b:editor", calls),
        },
        override_managers={
            "wf-a": _Manager("wf-a", calls),
            "wf-b": _Manager("wf-b", calls),
        },
        cube_stack_container=SimpleNamespace(
            setCurrentWidget=lambda widget: calls.append(f"cube:set:{id(widget)}"),
            removeWidget=lambda widget: calls.append(f"cube:remove:{id(widget)}"),
        ),
        editor_panel_container=SimpleNamespace(
            setCurrentWidget=lambda widget: calls.append(f"editor:set:{id(widget)}"),
            removeWidget=lambda widget: calls.append(f"editor:remove:{id(widget)}"),
        ),
        workflow_canvas_projection_coordinator=SimpleNamespace(
            project_workflow=lambda _workflows, workflow_id: calls.append(
                f"canvas:project:{workflow_id}"
            ),
        ),
        output_canvas_projection_coordinator=SimpleNamespace(
            prune_closed_workflow_images=(
                lambda _workflow_id, _closed, _remaining: calls.append("canvas:prune")
            ),
        ),
        input_canvas_state_service=SimpleNamespace(
            prune_closed_workflow_images=(
                lambda _closed, _remaining: calls.append("input:prune")
            ),
        ),
        workflow_ui_factory=SimpleNamespace(create_workflow_ui=create_new_workflow_ui),
        _pending_restored_workflow_snapshots={},
        _clear_all_model_field_load_progress=lambda: calls.append("model:clear"),
        generation_action_controller=SimpleNamespace(
            project_active_workflow_progress=lambda: calls.append("progress:project")
        ),
        workflow_progress_service=SimpleNamespace(
            remove_workflow=lambda workflow_id: calls.append(
                f"progress:remove:{workflow_id}"
            ),
            rename_workflow=lambda old, new: calls.append(
                f"progress:rename:{old}:{new}"
            ),
        ),
        refresh_active_workflow_surface=refresh_active_workflow_surface,
        search_overlay_controller=SimpleNamespace(
            position_search_box=lambda: calls.append("position")
        ),
        reopen_enabled_states=reopen_enabled_states,
        shell_frame_integration_controller=SimpleNamespace(
            set_reopen_closed_workflow_enabled=reopen_enabled_states.append,
        ),
        settings_route_controller=SimpleNamespace(
            show_workflow_workspace=lambda: calls.append("route:workflow"),
        ),
    )
    return view


class _DeferredSurfaceRefreshScheduler:
    """Surface-refresh scheduler double that records deferred requests."""

    def __init__(self) -> None:
        """Initialize an empty request log."""

        self.requests: list[dict[str, object]] = []

    def request(
        self,
        workflow_id: str,
        *,
        force_refresh: bool,
        reason: str,
        on_complete: object = None,
    ) -> None:
        """Record one deferred surface refresh request."""

        self.requests.append(
            {
                "workflow_id": workflow_id,
                "force_refresh": force_refresh,
                "reason": reason,
                "on_complete": on_complete,
            }
        )

    def cancel(self, workflow_id: str | None = None) -> None:
        """Remove pending requests for one workflow or all workflows."""

        if workflow_id is None:
            self.requests.clear()
            return
        self.requests = [
            request
            for request in self.requests
            if request["workflow_id"] != workflow_id
        ]

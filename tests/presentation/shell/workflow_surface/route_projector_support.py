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

"""Build workflow route-projection test doubles."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.domain.workflow import WorkflowState
from substitute.presentation.shell.workflow_route_projector import (
    WorkflowRouteProjector,
)
from substitute.presentation.shell.main_window_canvas_route_adapter import (
    MainWindowCanvasRouteAdapter,
)
from substitute.presentation.shell.main_window_override_surface_adapter import (
    MainWindowOverrideSurfaceAdapter,
)
from substitute.presentation.shell.main_window_workflow_activity_adapter import (
    MainWindowWorkflowActivityAdapter,
)
from substitute.presentation.shell.main_window_workflow_route_adapter import (
    MainWindowWorkflowRouteAdapter,
)
from substitute.presentation.shell.workflow_surface_invalidation import (
    WorkflowSurfaceInvalidationService,
)
from substitute.presentation.shell.workflow_surface_registry import (
    WorkflowSurfaceRegistry,
)


class _TabBar:
    """Workflow tabbar double recording silent selection and unread state."""

    def __init__(self, calls: list[str]) -> None:
        """Store the shared call log."""

        self._calls = calls
        self.unread_updates: list[tuple[str, bool]] = []

    def select_workflow_tab(self, workflow_id: str, *, emit: bool = False) -> None:
        """Record tab selection requests."""

        self._calls.append(f"tab:{workflow_id}:{emit}")

    def set_workflow_unread_result(self, workflow_id: str, state: bool) -> None:
        """Record unread badge updates."""

        self.unread_updates.append((workflow_id, state))


class _Container:
    """Stacked-widget container double recording visible widget swaps."""

    def __init__(self, label: str, calls: list[str]) -> None:
        """Store label and shared call log."""

        self._label = label
        self._calls = calls

    def setCurrentWidget(self, widget: object) -> None:
        """Record the current widget by object id."""

        self._calls.append(f"{self._label}:{id(widget)}")


class _OverrideManager:
    """Override manager double recording shared-toolbar route projection."""

    def __init__(self, workflow_id: str, calls: list[str]) -> None:
        """Store workflow id and shared call log."""

        self._workflow_id = workflow_id
        self._calls = calls

    def sync_state_from_workflow(self) -> None:
        """Record state synchronization."""

        self._calls.append(f"overrides:{self._workflow_id}:sync")

    def rebuild_override_menu(self) -> None:
        """Record menu rebuild."""

        self._calls.append(f"overrides:{self._workflow_id}:menu")

    def rebuild_active_override_controls(self) -> None:
        """Record toolbar controls rebuild."""

        self._calls.append(f"overrides:{self._workflow_id}:controls")

    def detach_override_widgets(self) -> None:
        """Record toolbar detachment."""

        self._calls.append(f"overrides:{self._workflow_id}:detach")


def _build_projector_view() -> SimpleNamespace:
    """Build a route-projector view double with two materialized workflows."""

    calls: list[str] = []
    tabbar = _TabBar(calls)
    view = SimpleNamespace(
        calls=calls,
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wf-b",
            workflows={"wf-a": WorkflowState(), "wf-b": WorkflowState()},
        ),
        workflow_tabbar=tabbar,
        workflow_canvas_projection_coordinator=SimpleNamespace(
            project_workflow=lambda _workflows, workflow_id: calls.append(
                f"canvas:{workflow_id}"
            )
        ),
        cube_stacks={"wf-a": object(), "wf-b": object()},
        editor_panels={"wf-a": object(), "wf-b": object()},
        override_managers={
            "wf-a": _OverrideManager("wf-a", calls),
            "wf-b": _OverrideManager("wf-b", calls),
        },
        cube_stack_container=_Container("cube", calls),
        editor_panel_container=_Container("editor", calls),
        search_overlay_controller=SimpleNamespace(
            position_search_box=lambda: calls.append("position")
        ),
        editor_busy=SimpleNamespace(
            refresh_active_surface=lambda: calls.append("busy")
        ),
        generation_action_controller=SimpleNamespace(
            apply_generation_action_availability=lambda: calls.append("actions")
        ),
        cube_stack_presentation_controller=SimpleNamespace(
            activate_document_kind=lambda kind, *, animated: calls.append(
                f"presentation:{kind.value}:{animated}"
            )
        ),
        settings_route_controller=SimpleNamespace(
            show_workflow_workspace=lambda: calls.append("route")
        ),
        _pending_restored_workflow_snapshots={},
    )
    return view


def _build_projector(
    view: SimpleNamespace,
    invalidation: WorkflowSurfaceInvalidationService,
) -> WorkflowRouteProjector:
    """Build a projector with a registry over the view's surface maps."""

    registry = WorkflowSurfaceRegistry(
        editor_panels=view.editor_panels,
        cube_stacks=view.cube_stacks,
        override_managers=view.override_managers,
        workflows=view.workflow_session_service.workflows,
        surface_invalidation_service=invalidation,
    )
    return WorkflowRouteProjector(
        MainWindowWorkflowRouteAdapter(view),
        canvas_port=MainWindowCanvasRouteAdapter(view),
        override_port=MainWindowOverrideSurfaceAdapter(view),
        activity_port=MainWindowWorkflowActivityAdapter(view),
        surface_registry=registry,
        surface_invalidation_service=invalidation,
    )

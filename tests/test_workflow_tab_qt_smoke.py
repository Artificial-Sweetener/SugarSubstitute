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

"""Qt smoke coverage for workflow tab route switching."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import cast

from PySide6.QtWidgets import QApplication, QStackedWidget, QWidget

from substitute.application.workflows import WorkflowSessionService, WorkflowTabService
from substitute.domain.workflow import CubeState, WorkflowState
from substitute.presentation.shell.workflow_workspace_coordinator import (
    WorkflowWorkspaceCoordinator,
    WorkflowWorkspaceView,
)


def _app() -> QApplication:
    """Return an active QApplication for lightweight widget construction."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


class _TabItem:
    """Workflow tab item double for smoke-route selection."""

    def __init__(self, workflow_id: str) -> None:
        """Store the workflow route key."""

        self._workflow_id = workflow_id

    def routeKey(self) -> str:
        """Return the workflow route key."""

        return self._workflow_id

    def text(self) -> str:
        """Return the displayed tab text."""

        return self._workflow_id

    def setRouteKey(self, key: str) -> None:
        """Replace the route key."""

        self._workflow_id = key

    def setText(self, text: str) -> None:
        """Accept label updates for protocol compatibility."""


class _TabBar:
    """Workflow tabbar double recording selected workflow ids."""

    def __init__(self, workflow_ids: list[str]) -> None:
        """Create items for workflow ids."""

        self.items = [_TabItem(workflow_id) for workflow_id in workflow_ids]
        self.itemMap = {item.routeKey(): item for item in self.items}
        self.selected: list[tuple[str, bool]] = []

    def addTab(self, routeKey: str, text: str) -> _TabItem:
        """Add a tab item."""

        del text
        item = _TabItem(routeKey)
        self.items.append(item)
        self.itemMap[routeKey] = item
        return item

    def count(self) -> int:
        """Return tab count."""

        return len(self.items)

    def currentIndex(self) -> int:
        """Return the current tab index."""

        if not self.selected:
            return 0
        return self.workflow_ids_in_order().index(self.selected[-1][0])

    def tabItem(self, index: int) -> _TabItem:
        """Return a tab item by index."""

        return self.items[index]

    def workflow_ids_in_order(self) -> list[str]:
        """Return route keys in visual order."""

        return [item.routeKey() for item in self.items]

    def select_workflow_tab(self, workflow_id: str, *, emit: bool = False) -> None:
        """Record selection."""

        self.selected.append((workflow_id, emit))

    def remove_workflow_tab(self, workflow_id: str, *, emit: bool = False) -> None:
        """Remove one tab item."""

        del emit
        item = self.itemMap.pop(workflow_id)
        self.items.remove(item)


class _EditorPanel(QWidget):
    """Projection-aware QWidget editor double."""

    def __init__(self, clean_workflow_ids: set[str]) -> None:
        """Store workflow ids that should report clean projection."""

        super().__init__()
        self._clean_workflow_ids = clean_workflow_ids
        self.load_calls: list[str] = []

    def current_projection_signature(
        self,
        *,
        workflow_id: str,
        cube_entries: list[tuple[str, object]],
        cube_states: dict[str, CubeState],
        stack_order: list[str],
    ) -> object:
        """Return a signature token for the workflow projection inputs."""

        del cube_entries, cube_states, stack_order
        return workflow_id

    def is_projection_clean(self, signature: object) -> bool:
        """Return whether the signature belongs to a projected workflow."""

        return str(signature) in self._clean_workflow_ids

    def clear_model_field_load_progress(self) -> None:
        """Accept generation-feedback progress cleanup."""

    def load_all_cubes(self, **kwargs: object) -> None:
        """Record editor projection work and run the optional completion callback."""

        workflow_id = cast(str, kwargs.get("projection_signature", ""))
        self.load_calls.append(workflow_id)
        on_complete = kwargs.get("on_complete")
        if callable(on_complete):
            cast(Callable[[], None], on_complete)()


class _Manager:
    """Override-manager double required by coordinator protocol."""

    def detach_override_widgets(self) -> None:
        """Accept toolbar detachment requests."""

    def _clear_all_override_widgets(self) -> None:
        """Accept toolbar clearing requests."""

    def dispose(self) -> None:
        """Accept disposal requests."""


class _WorkflowCanvasProjection:
    """Shared canvas projection double recording route projection order."""

    def __init__(self) -> None:
        """Initialize empty projection logs."""

        self.projected_workflow_ids: list[str] = []

    def project_workflow(self, workflows: object, active_workflow_id: str) -> None:
        """Record projected workflow ids."""

        del workflows
        self.projected_workflow_ids.append(active_workflow_id)


class _OutputCanvasProjection:
    """Output canvas projection double accepting closed-workflow pruning."""

    def prune_closed_workflow_images(
        self,
        closed_workflow_id: str,
        closed_workflow: object,
        remaining_workflows: object,
    ) -> None:
        """Accept prune requests for protocol compatibility."""

        del closed_workflow_id, closed_workflow, remaining_workflows


class _Scheduler:
    """Deferred scheduler double recording route-maintenance requests."""

    def __init__(self) -> None:
        """Initialize empty request log."""

        self.requests: list[str] = []

    def request(
        self,
        workflow_id: str,
        *,
        force_refresh: bool,
        reason: str,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        """Record deferred refresh requests."""

        del force_refresh, reason, on_complete
        self.requests.append(workflow_id)

    def cancel(self, workflow_id: str | None = None) -> None:
        """Accept cancellation requests."""

        del workflow_id


class _SmokeView:
    """Qt-backed view double for route-switch smoke coverage."""

    def __init__(self) -> None:
        """Create session, stacked widgets, and workflow-scoped widgets."""

        self.workflow_tab_service = WorkflowTabService()
        self.workflow_session_service = WorkflowSessionService(
            WorkflowState,
            default_workflow_id="wf-a",
        )
        self.workflow_session_service.add_workflow("wf-b")
        self.workflow_session_service.add_workflow("wf-c")
        for workflow_id in ("wf-a", "wf-b", "wf-c"):
            workflow = self.workflow_session_service.workflows[workflow_id]
            workflow.cubes["Cube"] = CubeState(
                cube_id=f"Owner/Repo/{workflow_id}.cube",
                version="1.0.0",
                alias="Cube",
                original_cube={},
                buffer={},
            )
            workflow.stack_order.append("Cube")
        self.workflow_session_service.activate_workflow("wf-a")
        self.workflow_tabbar = _TabBar(["wf-a", "wf-b", "wf-c"])
        self.workflow_canvas_projection_coordinator = _WorkflowCanvasProjection()
        self.output_canvas_projection_coordinator = _OutputCanvasProjection()
        self.input_canvas_state_service = SimpleNamespace(
            prune_closed_workflow_images=lambda *_args: None
        )
        self.cube_stack_container = QStackedWidget()
        self.editor_panel_container = QStackedWidget()
        clean_workflow_ids = {"wf-a", "wf-b"}
        self.cube_stacks = {
            workflow_id: QWidget() for workflow_id in ("wf-a", "wf-b", "wf-c")
        }
        self.editor_panels = {
            workflow_id: _EditorPanel(clean_workflow_ids)
            for workflow_id in ("wf-a", "wf-b", "wf-c")
        }
        self.override_managers = {
            workflow_id: _Manager() for workflow_id in ("wf-a", "wf-b", "wf-c")
        }
        for workflow_id in ("wf-a", "wf-b", "wf-c"):
            self.cube_stack_container.addWidget(self.cube_stacks[workflow_id])
            self.editor_panel_container.addWidget(self.editor_panels[workflow_id])
        self.cube_stack_container.setCurrentWidget(self.cube_stacks["wf-a"])
        self.editor_panel_container.setCurrentWidget(self.editor_panels["wf-a"])
        self.route_keys: list[str] = []
        self.input_availability_refreshes: list[str] = []
        self.progress_projection_count = 0
        self.generation_action_controller = SimpleNamespace(
            project_active_workflow_progress=self.project_active_workflow_progress
        )
        self.canvas_route_controller = SimpleNamespace(
            refresh_input_canvas_availability=self._refresh_input_canvas_availability
        )
        self.search_overlay_controller = SimpleNamespace(
            position_search_box=lambda: None
        )
        self.workflow_ui_factory = SimpleNamespace(
            create_workflow_ui=self._unexpected_workflow_ui_creation
        )

    def _unexpected_workflow_ui_creation(
        self,
        workflow_id: str,
        *,
        set_as_current: bool = True,
    ) -> tuple[object, object]:
        """Raise if smoke coverage unexpectedly materializes new widgets."""

        raise AssertionError((workflow_id, set_as_current))

    def ensure_workflow_ui(
        self,
        workflow_id: str,
        *,
        set_as_current: bool = True,
    ) -> tuple[object, object]:
        """Return existing workflow UI without creating widgets."""

        del set_as_current
        return self.cube_stacks[workflow_id], self.editor_panels[workflow_id]

    def refresh_active_workflow_surface(
        self,
        *,
        force_refresh: bool = False,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        """Raise if a clean tab switch performs synchronous editor refresh."""

        del force_refresh, on_complete
        raise AssertionError("clean tab switch refreshed editor")

    def _clear_all_model_field_load_progress(self) -> None:
        """Accept active transition cleanup."""

    def show_workflow_workspace(self) -> None:
        """Record workflow workspace route display."""

        self.route_keys.append("workflow")

    def set_active_workspace_route(self, workflow_id: str) -> None:
        """Record active route key."""

        self.route_keys.append(workflow_id)

    def _refresh_input_canvas_availability(self) -> None:
        """Record input canvas availability refresh for active workflow."""

        self.input_availability_refreshes.append(
            self.workflow_session_service.active_workflow_id
        )

    def project_active_workflow_progress(self) -> None:
        """Record progress projection for the active workflow."""

        self.progress_projection_count += 1


def test_qt_smoke_workflow_tabs_swap_widgets_and_shared_canvas() -> None:
    """Real Qt stacked widgets should route warm tabs without editor rebuilds."""

    _app()
    view = _SmokeView()
    scheduler = _Scheduler()
    coordinator = WorkflowWorkspaceCoordinator(
        cast(WorkflowWorkspaceView, view),
        surface_refresh_scheduler=scheduler,
    )
    editor_a = view.editor_panels["wf-a"]
    editor_b = view.editor_panels["wf-b"]
    editor_c = view.editor_panels["wf-c"]
    cube_a = view.cube_stacks["wf-a"]
    cube_b = view.cube_stacks["wf-b"]
    cube_c = view.cube_stacks["wf-c"]

    coordinator.activate_workflow("wf-b")
    coordinator.activate_workflow("wf-c")
    coordinator.activate_workflow("wf-a")

    assert view.editor_panels["wf-a"] is editor_a
    assert view.editor_panels["wf-b"] is editor_b
    assert view.editor_panels["wf-c"] is editor_c
    assert view.cube_stacks["wf-a"] is cube_a
    assert view.cube_stacks["wf-b"] is cube_b
    assert view.cube_stacks["wf-c"] is cube_c
    assert view.editor_panel_container.currentWidget() is editor_a
    assert view.cube_stack_container.currentWidget() is cube_a
    assert view.workflow_canvas_projection_coordinator.projected_workflow_ids == [
        "wf-b",
        "wf-c",
        "wf-a",
    ]
    assert scheduler.requests == ["wf-c"]
    assert editor_a.load_calls == []
    assert editor_b.load_calls == []
    assert editor_c.load_calls == []

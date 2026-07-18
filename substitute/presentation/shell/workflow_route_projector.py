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

"""Project the selected workflow route into visible shell surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from substitute.presentation.shell.workflow_route_ports import (
    CanvasRouteProjectionPort,
    OverrideRouteProjectionPort,
    WorkflowActivityPort,
    WorkflowRoutePort,
)
from substitute.presentation.shell.workflow_surface_invalidation import (
    WorkflowSurface,
)
from substitute.presentation.shell.workflow_surface_ports import (
    WorkflowSurfaceInvalidationPort,
)
from substitute.presentation.shell.workflow_surface_registry import (
    WorkflowSurfaceRegistry,
)
from substitute.presentation.shell.workflow_surface_results import (
    SurfaceRefreshStatus,
)
from substitute.shared.logging.logger import elapsed_ms_since, get_logger, log_debug

_LOGGER = get_logger("presentation.shell.workflow_route_projector")


@dataclass(frozen=True, slots=True)
class WorkflowRouteProjectionResult:
    """Summarize one immediate workflow route projection."""

    workflow_id: str
    created_widgets: bool
    editor_panel_present: bool
    cube_stack_present: bool
    canvas_projected: bool
    canvas_projection_elapsed_ms: float
    ensure_workflow_ui_elapsed_ms: float
    show_route_elapsed_ms: float
    tab_select_elapsed_ms: float
    cube_stack_swap_elapsed_ms: float
    editor_panel_swap_elapsed_ms: float
    override_projection_elapsed_ms: float
    input_canvas_availability_elapsed_ms: float
    overlay_refresh_elapsed_ms: float
    activity_badge_elapsed_ms: float
    overrides_projected: bool
    activity_cleared: bool
    route_projection_elapsed_ms: float


class WorkflowRouteProjector:
    """Own the synchronous, lightweight workflow route switch path."""

    def __init__(
        self,
        route_port: WorkflowRoutePort,
        *,
        canvas_port: CanvasRouteProjectionPort,
        override_port: OverrideRouteProjectionPort | None = None,
        activity_port: WorkflowActivityPort | None,
        surface_registry: WorkflowSurfaceRegistry,
        surface_invalidation_service: WorkflowSurfaceInvalidationPort,
    ) -> None:
        """Store narrow shell dependencies for immediate route projection."""

        self._route_port = route_port
        self._canvas_port = canvas_port
        self._override_port = override_port
        self._activity_port = activity_port
        self._surface_registry = surface_registry
        self._surface_invalidation_service = surface_invalidation_service

    def project(
        self,
        workflow_id: str,
        *,
        project_shared_canvas: bool = True,
    ) -> WorkflowRouteProjectionResult:
        """Synchronously show cached workflow widgets and shared route state."""

        started_at = perf_counter()
        log_debug(
            _LOGGER,
            "workflow route projector started",
            workflow_id=workflow_id,
            project_shared_canvas=project_shared_canvas,
            active_workflow_id=self._route_port.active_workflow_id,
        )
        phase_started_at = perf_counter()
        ui_pair = self._route_port.ensure_workflow_ui(
            workflow_id,
            set_as_current=False,
        )
        ensure_workflow_ui_elapsed_ms = elapsed_ms_since(phase_started_at)

        phase_started_at = perf_counter()
        self._route_port.show_workflow_workspace()
        self._route_port.set_active_workspace_route(workflow_id)
        show_route_elapsed_ms = elapsed_ms_since(phase_started_at)

        phase_started_at = perf_counter()
        self._route_port.select_workflow_tab(workflow_id, emit=False)
        tab_select_elapsed_ms = elapsed_ms_since(phase_started_at)

        phase_started_at = perf_counter()
        cube_stack_present = self._route_port.set_current_cube_stack(workflow_id)
        cube_stack_swap_elapsed_ms = elapsed_ms_since(phase_started_at)

        phase_started_at = perf_counter()
        editor_panel_present = self._route_port.set_current_editor_panel(workflow_id)
        editor_panel_swap_elapsed_ms = elapsed_ms_since(phase_started_at)

        self._route_port.present_cube_stack_for_workflow(workflow_id, animated=True)

        phase_started_at = perf_counter()
        overrides_projected = self._project_shared_overrides(workflow_id)
        override_projection_elapsed_ms = elapsed_ms_since(phase_started_at)

        canvas_projected = False
        canvas_elapsed_ms = 0.0
        input_canvas_availability_elapsed_ms = 0.0
        if project_shared_canvas:
            phase_started_at = perf_counter()
            canvas_result = self._canvas_port.project_workflow_canvas(workflow_id)
            canvas_projected = canvas_result.status is SurfaceRefreshStatus.SUCCESS
            canvas_elapsed_ms = canvas_result.elapsed_ms
            if canvas_elapsed_ms <= 0.0:
                canvas_elapsed_ms = elapsed_ms_since(phase_started_at)
            if canvas_result.cleanable:
                self._surface_invalidation_service.mark_clean(
                    workflow_id,
                    {WorkflowSurface.CANVAS},
                )
                phase_started_at = perf_counter()
                self._canvas_port.refresh_input_canvas_availability(workflow_id)
                input_canvas_availability_elapsed_ms = elapsed_ms_since(
                    phase_started_at
                )

        phase_started_at = perf_counter()
        self._route_port.position_search_box()
        self._route_port.refresh_editor_busy_surface()
        overlay_refresh_elapsed_ms = elapsed_ms_since(phase_started_at)

        phase_started_at = perf_counter()
        activity_cleared = self._mark_workflow_seen(workflow_id)
        activity_badge_elapsed_ms = elapsed_ms_since(phase_started_at)

        result = WorkflowRouteProjectionResult(
            workflow_id=workflow_id,
            created_widgets=ui_pair.created,
            editor_panel_present=editor_panel_present,
            cube_stack_present=cube_stack_present,
            canvas_projected=canvas_projected,
            canvas_projection_elapsed_ms=canvas_elapsed_ms,
            ensure_workflow_ui_elapsed_ms=ensure_workflow_ui_elapsed_ms,
            show_route_elapsed_ms=show_route_elapsed_ms,
            tab_select_elapsed_ms=tab_select_elapsed_ms,
            cube_stack_swap_elapsed_ms=cube_stack_swap_elapsed_ms,
            editor_panel_swap_elapsed_ms=editor_panel_swap_elapsed_ms,
            override_projection_elapsed_ms=override_projection_elapsed_ms,
            input_canvas_availability_elapsed_ms=input_canvas_availability_elapsed_ms,
            overlay_refresh_elapsed_ms=overlay_refresh_elapsed_ms,
            activity_badge_elapsed_ms=activity_badge_elapsed_ms,
            overrides_projected=overrides_projected,
            activity_cleared=activity_cleared,
            route_projection_elapsed_ms=elapsed_ms_since(started_at),
        )
        log_debug(
            _LOGGER,
            "workflow route projector completed",
            workflow_id=workflow_id,
            created_widgets=result.created_widgets,
            editor_panel_present=result.editor_panel_present,
            cube_stack_present=result.cube_stack_present,
            canvas_projected=result.canvas_projected,
            canvas_projection_elapsed_ms=f"{result.canvas_projection_elapsed_ms:.3f}",
            ensure_workflow_ui_elapsed_ms=(
                f"{result.ensure_workflow_ui_elapsed_ms:.3f}"
            ),
            show_route_elapsed_ms=f"{result.show_route_elapsed_ms:.3f}",
            tab_select_elapsed_ms=f"{result.tab_select_elapsed_ms:.3f}",
            cube_stack_swap_elapsed_ms=f"{result.cube_stack_swap_elapsed_ms:.3f}",
            editor_panel_swap_elapsed_ms=f"{result.editor_panel_swap_elapsed_ms:.3f}",
            override_projection_elapsed_ms=(
                f"{result.override_projection_elapsed_ms:.3f}"
            ),
            input_canvas_availability_elapsed_ms=(
                f"{result.input_canvas_availability_elapsed_ms:.3f}"
            ),
            overlay_refresh_elapsed_ms=f"{result.overlay_refresh_elapsed_ms:.3f}",
            activity_badge_elapsed_ms=f"{result.activity_badge_elapsed_ms:.3f}",
            overrides_projected=result.overrides_projected,
            activity_cleared=result.activity_cleared,
            route_projection_elapsed_ms=f"{result.route_projection_elapsed_ms:.3f}",
        )
        return result

    def _project_shared_overrides(self, workflow_id: str) -> bool:
        """Project selected workflow overrides into the shared toolbar."""

        if self._override_port is None:
            return False
        result = self._override_port.project_workflow_overrides(workflow_id)
        return result.status is SurfaceRefreshStatus.SUCCESS

    def _mark_workflow_seen(self, workflow_id: str) -> bool:
        """Clear unread workflow result activity when an activity port exists."""

        if self._activity_port is None:
            return False
        return self._activity_port.mark_workflow_seen(workflow_id)


__all__ = [
    "WorkflowRouteProjectionResult",
    "WorkflowRouteProjector",
]

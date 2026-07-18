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

"""Adapt MainWindow canvas routing to its narrow projection port."""

from __future__ import annotations

from time import perf_counter


from substitute.presentation.shell.workflow_surface_invalidation import (
    WorkflowSurface,
)
from substitute.presentation.shell.workflow_surface_results import (
    SurfaceRefreshResult,
    SurfaceRefreshStatus,
    surface_result,
)
from substitute.shared.logging.logger import (
    elapsed_ms_since,
    get_logger,
    log_exception,
)

_LOGGER = get_logger("presentation.shell.main_window_canvas_route_adapter")
_RECONCILER_LOGGER = get_logger("presentation.shell.workflow_surface_reconciler")


class MainWindowCanvasRouteAdapter:
    """Expose shared canvas route projection through a narrow port."""

    def __init__(self, shell: object) -> None:
        """Store the shell object behind a canvas projection API."""

        self._shell = shell

    def project_workflow_canvas(self, workflow_id: str) -> SurfaceRefreshResult:
        """Project shared canvas panes for the selected workflow."""

        started_at = perf_counter()
        session = getattr(self._shell, "workflow_session_service", None)
        active_workflow_id = str(getattr(session, "active_workflow_id", ""))
        if workflow_id != active_workflow_id:
            return surface_result(
                workflow_id=workflow_id,
                surface=WorkflowSurface.CANVAS,
                status=SurfaceRefreshStatus.SKIPPED_STALE,
                operation="project_workflow_canvas",
                elapsed_ms=elapsed_ms_since(started_at),
                cleanable=False,
            )
        canvas_projection_coordinator = getattr(
            self._shell,
            "workflow_canvas_projection_coordinator",
            None,
        )
        project_workflow = getattr(
            canvas_projection_coordinator,
            "project_workflow",
            None,
        )
        workflows = getattr(session, "workflows", {})
        if not callable(project_workflow):
            return surface_result(
                workflow_id=workflow_id,
                surface=WorkflowSurface.CANVAS,
                status=SurfaceRefreshStatus.SKIPPED_MISSING,
                operation="project_workflow_canvas",
                elapsed_ms=elapsed_ms_since(started_at),
                cleanable=False,
                error="workflow_canvas_projection_coordinator.project_workflow missing",
            )
        try:
            project_workflow(workflows, workflow_id)
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to project workflow canvas route",
                workflow_id=workflow_id,
                surface=WorkflowSurface.CANVAS.value,
                operation="project_workflow_canvas",
                error=error,
            )
            return surface_result(
                workflow_id=workflow_id,
                surface=WorkflowSurface.CANVAS,
                status=SurfaceRefreshStatus.FAILED,
                operation="project_workflow_canvas",
                elapsed_ms=elapsed_ms_since(started_at),
                cleanable=False,
                error=repr(error),
            )
        return surface_result(
            workflow_id=workflow_id,
            surface=WorkflowSurface.CANVAS,
            status=SurfaceRefreshStatus.SUCCESS,
            operation="project_workflow_canvas",
            elapsed_ms=elapsed_ms_since(started_at),
        )

    def refresh_input_canvas_availability(
        self,
        workflow_id: str,
    ) -> SurfaceRefreshResult:
        """Refresh input-canvas availability for the active workflow."""

        started_at = perf_counter()
        if workflow_id != self._active_workflow_id():
            return surface_result(
                workflow_id=workflow_id,
                surface=WorkflowSurface.CANVAS,
                status=SurfaceRefreshStatus.SKIPPED_STALE,
                operation="refresh_input_canvas_availability",
                elapsed_ms=elapsed_ms_since(started_at),
                cleanable=False,
            )
        refresh_input_canvas_availability = getattr(
            getattr(self._shell, "canvas_route_controller", None),
            "refresh_input_canvas_availability",
            None,
        )
        if not callable(refresh_input_canvas_availability):
            return surface_result(
                workflow_id=workflow_id,
                surface=WorkflowSurface.CANVAS,
                status=SurfaceRefreshStatus.SKIPPED_MISSING,
                operation="refresh_input_canvas_availability",
                elapsed_ms=elapsed_ms_since(started_at),
                cleanable=False,
                error="canvas_route_controller.refresh_input_canvas_availability missing",
            )
        try:
            refresh_input_canvas_availability()
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to refresh input canvas availability",
                workflow_id=workflow_id,
                surface=WorkflowSurface.CANVAS.value,
                operation="refresh_input_canvas_availability",
                error=error,
            )
            return surface_result(
                workflow_id=workflow_id,
                surface=WorkflowSurface.CANVAS,
                status=SurfaceRefreshStatus.FAILED,
                operation="refresh_input_canvas_availability",
                elapsed_ms=elapsed_ms_since(started_at),
                cleanable=False,
                error=repr(error),
            )
        return surface_result(
            workflow_id=workflow_id,
            surface=WorkflowSurface.CANVAS,
            status=SurfaceRefreshStatus.SUCCESS,
            operation="refresh_input_canvas_availability",
            elapsed_ms=elapsed_ms_since(started_at),
        )

    def _active_workflow_id(self) -> str:
        """Return the active workflow id known to the shell."""

        session = getattr(self._shell, "workflow_session_service", None)
        return str(getattr(session, "active_workflow_id", ""))

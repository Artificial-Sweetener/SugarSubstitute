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

"""Adapt MainWindow generation availability to its surface port."""

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

_LOGGER = get_logger("presentation.shell.main_window_generation_availability_adapter")
_RECONCILER_LOGGER = get_logger("presentation.shell.workflow_surface_reconciler")


class MainWindowGenerationAvailabilityAdapter:
    """Expose generation and input availability refresh through a narrow port."""

    def __init__(self, shell: object) -> None:
        """Store the shell object behind an availability API."""

        self._shell = shell

    def refresh_generation_availability(
        self,
        workflow_id: str,
    ) -> SurfaceRefreshResult:
        """Refresh generation action availability for one workflow."""

        return self._run(
            workflow_id,
            operation="refresh_generation_availability",
            surface=WorkflowSurface.GENERATION_AVAILABILITY,
            action_name="generation_action_controller.apply_generation_action_availability",
        )

    def refresh_input_availability(self, workflow_id: str) -> SurfaceRefreshResult:
        """Refresh active input-canvas availability for one workflow."""

        return self._run(
            workflow_id,
            operation="refresh_input_availability",
            surface=WorkflowSurface.GENERATION_AVAILABILITY,
            action_name="canvas_route_controller.refresh_input_canvas_availability",
        )

    def _run(
        self,
        workflow_id: str,
        *,
        operation: str,
        surface: WorkflowSurface,
        action_name: str,
    ) -> SurfaceRefreshResult:
        """Run one shell availability method with result reporting."""

        started_at = perf_counter()
        if workflow_id != self._active_workflow_id():
            return surface_result(
                workflow_id=workflow_id,
                surface=surface,
                status=SurfaceRefreshStatus.SKIPPED_STALE,
                operation=operation,
                elapsed_ms=elapsed_ms_since(started_at),
                cleanable=False,
            )
        action = self._resolve_action(action_name)
        if not callable(action):
            return surface_result(
                workflow_id=workflow_id,
                surface=surface,
                status=SurfaceRefreshStatus.SKIPPED_MISSING,
                operation=operation,
                elapsed_ms=elapsed_ms_since(started_at),
                cleanable=False,
                error=f"{action_name} missing",
            )
        try:
            action()
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to refresh workflow availability",
                workflow_id=workflow_id,
                surface=surface.value,
                operation=operation,
                error=error,
            )
            return surface_result(
                workflow_id=workflow_id,
                surface=surface,
                status=SurfaceRefreshStatus.FAILED,
                operation=operation,
                elapsed_ms=elapsed_ms_since(started_at),
                cleanable=False,
                error=repr(error),
            )
        return surface_result(
            workflow_id=workflow_id,
            surface=surface,
            status=SurfaceRefreshStatus.SUCCESS,
            operation=operation,
            elapsed_ms=elapsed_ms_since(started_at),
        )

    def _active_workflow_id(self) -> str:
        """Return the active workflow id known to the shell."""

        session = getattr(self._shell, "workflow_session_service", None)
        return str(getattr(session, "active_workflow_id", ""))

    def _resolve_action(self, action_name: str) -> object:
        """Resolve a shell action, including one level of composed ownership."""

        owner: object = self._shell
        for segment in action_name.split("."):
            owner = getattr(owner, segment, None)
            if owner is None:
                return None
        return owner

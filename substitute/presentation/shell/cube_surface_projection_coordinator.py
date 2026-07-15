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

"""Project a newly added durable cube across active shell surfaces."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from substitute.shared.logging.logger import get_logger, log_info, log_warning

_LOGGER = get_logger("presentation.shell.cube_surface_projection_coordinator")


class CubeSurfaceActionsProtocol(Protocol):
    """Describe incremental cube-surface refresh and activation operations."""

    def refresh_loaded_cube_surface_async(
        self,
        workflow_id: str,
        cube_alias: str,
        on_complete: Callable[[bool], None],
        *,
        wait_for_complete: bool = False,
    ) -> None:
        """Insert or refresh one cube section asynchronously."""

    def activate_loaded_cube(self, workflow_id: str, cube_alias: str) -> None:
        """Select and reveal one projected cube."""


class ActiveSurfaceRefresherProtocol(Protocol):
    """Describe the structural fallback used when incremental insertion fails."""

    def refresh_active_workflow_surface(
        self,
        *,
        force_refresh: bool = False,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        """Refresh active workflow surfaces and notify completion."""


class CubeSurfaceProjectionCoordinator:
    """Finish editor, canvas, and navigation projection for an added cube."""

    def __init__(
        self,
        *,
        surface_actions: CubeSurfaceActionsProtocol,
        active_surface_refresher: ActiveSurfaceRefresherProtocol,
        materialize_input_canvas: Callable[[str, str], None],
    ) -> None:
        """Store presentation collaborators for post-addition projection."""

        self._surface_actions = surface_actions
        self._active_surface_refresher = active_surface_refresher
        self._materialize_input_canvas = materialize_input_canvas

    def project_added_cube(
        self,
        workflow_id: str,
        cube_alias: str,
        *,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        """Project, materialize, and activate one newly added cube."""

        completed = False

        def finish_projection() -> None:
            """Materialize live canvas state and activate exactly once."""

            nonlocal completed
            if completed:
                return
            completed = True
            self._materialize_input_canvas(workflow_id, cube_alias)
            self._surface_actions.activate_loaded_cube(workflow_id, cube_alias)
            log_info(
                _LOGGER,
                "Completed added cube surface projection",
                workflow_id=workflow_id,
                cube_alias=cube_alias,
            )
            if on_complete is not None:
                on_complete()

        def finish_incremental(refreshed: bool) -> None:
            """Use structural reconciliation when incremental insertion is unavailable."""

            if refreshed:
                finish_projection()
                return
            log_warning(
                _LOGGER,
                "Added cube incremental projection unavailable; using structural refresh",
                workflow_id=workflow_id,
                cube_alias=cube_alias,
            )
            self._active_surface_refresher.refresh_active_workflow_surface(
                force_refresh=True,
                on_complete=finish_projection,
            )

        self._surface_actions.refresh_loaded_cube_surface_async(
            workflow_id,
            cube_alias,
            finish_incremental,
            wait_for_complete=True,
        )


__all__ = ["CubeSurfaceProjectionCoordinator"]

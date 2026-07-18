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

"""Define narrow ports for immediate workflow route projection."""

from __future__ import annotations

from typing import Protocol

from substitute.presentation.shell.workflow_surface_results import (
    SurfaceRefreshResult,
    WorkflowUiSurfaces,
)


class WorkflowRoutePort(Protocol):
    """Expose only shell route operations allowed during tab selection."""

    @property
    def active_workflow_id(self) -> str:
        """Return the active workflow id known to the workflow session."""

    def show_workflow_workspace(self) -> None:
        """Show the workflow workspace route."""

    def set_active_workspace_route(self, workflow_id: str) -> None:
        """Record the selected workflow route as active."""

    def select_workflow_tab(self, workflow_id: str, *, emit: bool = False) -> None:
        """Select a workflow tab without necessarily emitting user intent."""

    def ensure_workflow_ui(
        self,
        workflow_id: str,
        *,
        set_as_current: bool = True,
    ) -> WorkflowUiSurfaces:
        """Ensure workflow-scoped widgets exist for route projection."""

    def set_current_cube_stack(self, workflow_id: str) -> bool:
        """Show the cached cube stack for the workflow."""

    def set_current_editor_panel(self, workflow_id: str) -> bool:
        """Show the cached editor panel for the workflow."""

    def present_cube_stack_for_workflow(
        self,
        workflow_id: str,
        *,
        animated: bool = True,
    ) -> None:
        """Project document-kind availability after destination surfaces are active."""

    def position_search_box(self) -> None:
        """Reposition lightweight editor overlays."""

    def refresh_editor_busy_surface(self) -> None:
        """Refresh active editor busy presentation."""


class CanvasRouteProjectionPort(Protocol):
    """Expose shared canvas route projection for selected workflows."""

    def project_workflow_canvas(self, workflow_id: str) -> SurfaceRefreshResult:
        """Project shared canvas panes for one workflow route."""

    def refresh_input_canvas_availability(
        self,
        workflow_id: str,
    ) -> SurfaceRefreshResult:
        """Refresh input-canvas availability for the selected workflow."""


class OverrideRouteProjectionPort(Protocol):
    """Expose shared override toolbar projection for selected workflows."""

    def project_workflow_overrides(self, workflow_id: str) -> SurfaceRefreshResult:
        """Project the selected workflow's override controls into the shared toolbar."""


class WorkflowActivityPort(Protocol):
    """Expose workflow unread/activity state used during route projection."""

    def mark_workflow_seen(self, workflow_id: str) -> bool:
        """Clear unread activity for one workflow when present."""


__all__ = [
    "CanvasRouteProjectionPort",
    "OverrideRouteProjectionPort",
    "WorkflowActivityPort",
    "WorkflowRoutePort",
]

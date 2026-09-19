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

"""Compose typed workflow surface reconciliation for the main window."""

from __future__ import annotations

from substitute.presentation.shell.main_window_cube_stack_surface_adapter import (
    MainWindowCubeStackSurfaceAdapter,
)
from substitute.presentation.shell.main_window_editor_surface_adapter import (
    MainWindowEditorSurfaceAdapter,
)
from substitute.presentation.shell.main_window_generation_availability_adapter import (
    MainWindowGenerationAvailabilityAdapter,
)
from substitute.presentation.shell.main_window_workflow_session_state_adapter import (
    MainWindowWorkflowSessionStateAdapter,
)
from substitute.presentation.shell.workflow_route_ports import CanvasRouteProjectionPort
from substitute.presentation.shell.workflow_surface_ports import (
    OverrideSurfacePort,
    WorkflowSurfaceInvalidationPort,
)
from substitute.presentation.shell.workflow_surface_reconciler import (
    WorkflowSurfaceReconciler,
)


def build_main_window_workflow_surface_reconciler(
    view: object,
    *,
    canvas_port: CanvasRouteProjectionPort,
    override_port: OverrideSurfacePort,
    surface_invalidation_service: WorkflowSurfaceInvalidationPort,
) -> WorkflowSurfaceReconciler:
    """Build the main-window adapter graph for workflow surface maintenance."""

    return WorkflowSurfaceReconciler(
        MainWindowWorkflowSessionStateAdapter(view),
        canvas_port=canvas_port,
        editor_port=MainWindowEditorSurfaceAdapter(view),
        cube_stack_port=MainWindowCubeStackSurfaceAdapter(view),
        override_port=override_port,
        generation_port=MainWindowGenerationAvailabilityAdapter(view),
        surface_invalidation_service=surface_invalidation_service,
    )


__all__ = ["build_main_window_workflow_surface_reconciler"]

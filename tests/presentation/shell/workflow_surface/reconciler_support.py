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

"""Compose workflow surface reconciliation state."""

from __future__ import annotations

from types import SimpleNamespace


from substitute.presentation.shell.generation_action_controller import (
    GenerationActionController,
)
from substitute.presentation.shell.generation_action_state import (
    GenerationActionPresentation,
)
from substitute.presentation.shell.workflow_surface_invalidation import (
    WorkflowSurfaceInvalidationService,
)
from substitute.presentation.shell.workflow_surface_reconciler import (
    WorkflowSurfaceReconciler,
)


from tests.presentation.shell.workflow_surface.reconciler_fakes import (
    _CanvasPort,
    _EditorPort,
    _GenerationPort,
    _OverridePort,
    _SessionPort,
)


def _build_reconciler(
    invalidation: WorkflowSurfaceInvalidationService,
    *,
    active_workflow_id: str = "wf-a",
) -> tuple[
    WorkflowSurfaceReconciler,
    list[str],
    _CanvasPort,
    _EditorPort,
    _OverridePort,
    _GenerationPort,
]:
    """Build a reconciler and expose its fake ports."""

    calls: list[str] = []
    canvas = _CanvasPort(calls)
    editor = _EditorPort(calls)
    overrides = _OverridePort(calls)
    generation = _GenerationPort(calls)
    reconciler = WorkflowSurfaceReconciler(
        _SessionPort(active_workflow_id),
        canvas_port=canvas,
        editor_port=editor,
        override_port=overrides,
        generation_port=generation,
        surface_invalidation_service=invalidation,
    )
    return reconciler, calls, canvas, editor, overrides, generation


class _GenerationActionCluster:
    """Record projected generation titlebar presentations."""

    def __init__(self) -> None:
        """Initialize with no projected presentations."""

        self.presentations: list[GenerationActionPresentation] = []

    def apply_generation_presentation(
        self,
        presentation: GenerationActionPresentation,
    ) -> None:
        """Record one generated titlebar presentation."""

        self.presentations.append(presentation)


def _active_surface_shell(
    *,
    workflow_id: str,
    workflow: object,
    editor_panel: object,
    override_manager: object,
) -> SimpleNamespace:
    """Build a shell fake exposing active workflow surface collaborators."""

    shell = SimpleNamespace(
        workflow_session_service=SimpleNamespace(
            active_workflow_id=workflow_id,
            workflows={workflow_id: workflow},
        ),
        get_active_workflow=lambda: workflow,
        active_editor_panel=editor_panel,
        editor_panels={workflow_id: editor_panel},
        active_override_manager=override_manager,
        override_managers={workflow_id: override_manager},
        workflow_canvas_projection_coordinator=SimpleNamespace(
            project_workflow=lambda _workflows, _workflow_id: None
        ),
        canvas_route_controller=SimpleNamespace(
            refresh_input_canvas_availability=lambda: None
        ),
        generationActionCluster=_GenerationActionCluster(),
        generation_titlebar_control_registry=None,
        _current_generate_mode="generate",
        _backend_state="ready",
        _active_workspace_route=workflow_id,
        _detached_for_gui_reload=False,
        workspace_generation_controller=SimpleNamespace(is_continuous_active=False),
        generation_job_queue_service=SimpleNamespace(
            has_active_job=lambda: False,
            has_cancellable_jobs=lambda: False,
            jobs=lambda: (),
        ),
        generation_queue_controller=SimpleNamespace(panel_visible=False),
    )
    shell.generation_action_controller = GenerationActionController(shell)
    return shell


def _record_bool(calls: list[str], label: str, result: bool) -> bool:
    """Record an action label and return a configured boolean result."""

    calls.append(label)
    return result

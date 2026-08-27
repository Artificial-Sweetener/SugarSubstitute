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

"""Test workspace output navigation actions."""

from __future__ import annotations

from types import SimpleNamespace


from substitute.application.workflows.output_navigation_session_service import (
    OutputNavigationSessionService,
)
from substitute.application.workflows.output_scene_navigation_selection import (
    OutputSceneNavigationSelection,
)
from substitute.domain.workflow import (
    OutputCompareSelection,
    OutputCompareState,
    OutputFocusMode,
    WorkflowState,
)


from tests.presentation.shell.canvas_actions.support import (
    _import_module,
)


def test_active_output_selection_records_manual_uuid() -> None:
    """Concrete output selection should delegate to OutputCanvasStateService."""

    mod = _import_module()
    workflow = WorkflowState()
    calls: list[tuple[object, str]] = []
    view = SimpleNamespace(
        get_active_workflow=lambda: workflow,
        workflow_session_service=SimpleNamespace(active_workflow_id="wf"),
        output_navigation_session_service=OutputNavigationSessionService(),
        output_canvas_focus_service=SimpleNamespace(
            set_active_output_uuid=lambda active_workflow, uuid_str: calls.append(
                (active_workflow, uuid_str)
            )
        ),
    )

    mod.WorkspaceCanvasActions(view).on_active_output_changed("out-1")

    assert calls == [(workflow, "out-1")]
    assert workflow.output_focus_mode is OutputFocusMode.MANUAL


def test_active_output_grid_selection_records_manual_grid() -> None:
    """Grid output selection should delegate to OutputCanvasStateService."""

    mod = _import_module()
    workflow = WorkflowState()
    calls: list[tuple[object, str, object]] = []
    view = SimpleNamespace(
        get_active_workflow=lambda: workflow,
        workflow_session_service=SimpleNamespace(active_workflow_id="wf"),
        output_navigation_session_service=OutputNavigationSessionService(),
        output_canvas_focus_service=SimpleNamespace(
            set_active_output_grid=lambda active_workflow, source_key, scene_key=None: (
                calls.append((active_workflow, source_key, scene_key))
            )
        ),
    )

    mod.WorkspaceCanvasActions(view).on_active_output_grid_changed("wf:node")

    assert calls == [(workflow, "wf:node", None)]
    assert workflow.output_focus_mode is OutputFocusMode.MANUAL


def test_active_output_scene_selection_records_manual_scene() -> None:
    """Scene output selection should delegate to OutputCanvasStateService."""

    mod = _import_module()
    workflow = WorkflowState()
    calls: list[tuple[object, OutputSceneNavigationSelection]] = []
    view = SimpleNamespace(
        get_active_workflow=lambda: workflow,
        workflow_session_service=SimpleNamespace(active_workflow_id="wf"),
        output_navigation_session_service=OutputNavigationSessionService(),
        output_canvas_focus_service=SimpleNamespace(
            set_active_output_scene=lambda active_workflow, selection: calls.append(
                (active_workflow, selection)
            )
        ),
    )

    scene_selection = OutputSceneNavigationSelection(
        scene_key="scene-a",
        overview=False,
        source_key="source-a",
        set_index=0,
        image_id=None,
    )
    overview_selection = OutputSceneNavigationSelection(
        scene_key=None,
        overview=True,
        source_key=None,
        set_index=1,
        image_id=None,
    )
    actions = mod.WorkspaceCanvasActions(view)
    actions.on_active_output_scene_changed(scene_selection)
    actions.on_active_output_scene_changed(overview_selection)

    assert calls == [(workflow, scene_selection), (workflow, overview_selection)]
    assert workflow.output_focus_mode is OutputFocusMode.MANUAL


def test_output_compare_selection_records_compare_state() -> None:
    """Output compare changes should delegate to OutputCanvasStateService."""

    mod = _import_module()
    workflow = WorkflowState()
    calls: list[tuple[WorkflowState, OutputCompareState]] = []
    view = SimpleNamespace(
        get_active_workflow=lambda: workflow,
        workflow_session_service=SimpleNamespace(active_workflow_id="wf"),
        output_navigation_session_service=OutputNavigationSessionService(),
        output_canvas_focus_service=SimpleNamespace(
            set_output_compare_state=lambda active_workflow, state: calls.append(
                (active_workflow, state)
            )
        ),
    )
    state = OutputCompareState(
        enabled=True,
        base=OutputCompareSelection(None, 1, "source-a"),
        comparison=OutputCompareSelection(None, 1, "source-b"),
    )

    mod.WorkspaceCanvasActions(view).on_output_compare_changed(state)

    assert calls == [(workflow, state)]
    assert workflow.output_focus_mode is OutputFocusMode.MANUAL


def test_output_selection_intents_schedule_active_projection() -> None:
    """Persisted Output selection intents should schedule active workflow projection."""

    mod = _import_module()
    workflow = WorkflowState()
    scheduled: list[str] = []
    view = SimpleNamespace(
        get_active_workflow=lambda: workflow,
        workflow_session_service=SimpleNamespace(active_workflow_id="wf"),
        output_navigation_session_service=OutputNavigationSessionService(),
        output_canvas_focus_service=SimpleNamespace(
            set_active_output_uuid=lambda *_args: None,
            set_active_output_grid=lambda *_args, **_kwargs: None,
            set_active_output_scene=lambda *_args, **_kwargs: None,
            set_output_compare_state=lambda *_args: None,
        ),
        output_image_pipeline=SimpleNamespace(
            schedule_user_selected_output_projection=scheduled.append,
        ),
    )
    state = OutputCompareState(
        enabled=True,
        base=OutputCompareSelection(None, 1, "source-a"),
        comparison=OutputCompareSelection(None, 1, "source-b"),
    )
    actions = mod.WorkspaceCanvasActions(view)

    actions.on_active_output_changed("out-1")
    actions.on_active_output_grid_changed("wf:node")
    actions.on_active_output_scene_changed(
        OutputSceneNavigationSelection(
            scene_key="scene-a",
            overview=False,
            source_key="source-a",
            set_index=0,
            image_id=None,
        )
    )
    actions.on_output_compare_changed(state)

    assert scheduled == ["wf", "wf", "wf", "wf"]

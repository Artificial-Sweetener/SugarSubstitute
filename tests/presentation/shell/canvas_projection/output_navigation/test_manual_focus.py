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

"""Characterize manual output focus, scene selection, and comparison state."""

import uuid


from substitute.application.workflows.output_scene_navigation_selection import (
    OutputSceneNavigationSelection,
)
from substitute.domain.workflow import (
    ImageMeta,
    OutputCompareSelection,
    OutputCompareState,
    OutputFocusMode,
    WorkflowState,
)


from ..support.harness import (
    _build_service,
    _store_image_record,
)


def test_set_active_output_uuid_records_manual_source_and_set() -> None:
    """Concrete output selection should store manual source and set intent."""

    service, _input_pane, _output_pane, _output_canvas = _build_service()
    workflow = WorkflowState()
    first_id = uuid.uuid4()
    second_id = uuid.uuid4()
    workflow.output_image_uuids = [first_id, second_id]
    _store_image_record(
        service,
        first_id,
        ImageMeta(
            "wf",
            "Cube",
            1,
            "",
            "E:/one.png",
            source_key="wf:node",
        ),
    )
    _store_image_record(
        service,
        second_id,
        ImageMeta(
            "wf",
            "Cube",
            2,
            "",
            "E:/two.png",
            source_key="wf:node",
        ),
    )

    service.output_navigation_session_service.mark_user_navigation("wf", workflow)
    service.output_canvas_focus_service.set_active_output_uuid(workflow, str(second_id))

    assert workflow.output_focus_mode is OutputFocusMode.MANUAL
    assert workflow.active_output_uuid == second_id
    assert workflow.active_output_set_index == 2
    assert workflow.active_output_source_key == "wf:node"
    assert workflow.active_output_scene_key is None
    assert workflow.active_output_scene_overview is False


def test_set_active_output_uuid_records_manual_scene_and_scene_local_set() -> None:
    """Concrete scene output selection should store scene-local source/set intent."""

    service, _input_pane, _output_pane, _output_canvas = _build_service()
    workflow = WorkflowState()
    scene1_first = uuid.uuid4()
    scene1_second = uuid.uuid4()
    scene2_first = uuid.uuid4()
    workflow.output_image_uuids = [scene1_first, scene1_second, scene2_first]
    for image_id, image_number, scene_key in (
        (scene1_first, 1, "scene1"),
        (scene1_second, 2, "scene1"),
        (scene2_first, 1, "scene2"),
    ):
        _store_image_record(
            service,
            image_id,
            ImageMeta(
                "wf",
                "Cube",
                image_number,
                "",
                f"E:/{scene_key}_{image_number}.png",
                source_key="wf:node",
                scene_key=scene_key,
            ),
        )

    service.output_navigation_session_service.mark_user_navigation("wf", workflow)
    service.output_canvas_focus_service.set_active_output_uuid(
        workflow, str(scene2_first)
    )

    assert workflow.output_focus_mode is OutputFocusMode.MANUAL
    assert workflow.active_output_uuid == scene2_first
    assert workflow.active_output_set_index == 1
    assert workflow.active_output_source_key == "wf:node"
    assert workflow.active_output_scene_key == "scene2"
    assert workflow.active_output_scene_overview is False


def test_set_active_output_grid_records_manual_grid_intent() -> None:
    """Grid selection should store manual set-zero focus intent."""

    service, _input_pane, _output_pane, _output_canvas = _build_service()
    workflow = WorkflowState()
    workflow.active_output_uuid = uuid.uuid4()

    service.output_navigation_session_service.mark_user_navigation("wf", workflow)
    service.output_canvas_focus_service.set_active_output_grid(workflow, "wf:node")

    assert workflow.output_focus_mode is OutputFocusMode.MANUAL
    assert workflow.active_output_uuid is None
    assert workflow.active_output_set_index == 0
    assert workflow.active_output_source_key == "wf:node"
    assert workflow.active_output_scene_key is None
    assert workflow.active_output_scene_overview is False


def test_set_active_output_scene_records_manual_scene_intent() -> None:
    """Scene selection should store manual scene focus separately from source focus."""

    service, _input_pane, _output_pane, _output_canvas = _build_service()
    workflow = WorkflowState()
    workflow.active_output_uuid = uuid.uuid4()
    workflow.active_output_source_key = "wf:node"
    workflow.active_output_set_index = 0

    service.output_navigation_session_service.mark_user_navigation("wf", workflow)
    service.output_canvas_focus_service.set_active_output_scene(
        workflow,
        OutputSceneNavigationSelection(
            scene_key="scene2",
            overview=False,
            source_key="wf:node",
            set_index=0,
            image_id=None,
        ),
    )

    assert workflow.output_focus_mode is OutputFocusMode.MANUAL
    assert workflow.active_output_scene_key == "scene2"
    assert workflow.active_output_scene_overview is False
    assert workflow.active_output_source_key == "wf:node"
    assert workflow.active_output_set_index == 0
    assert workflow.active_output_uuid is None


def test_set_active_output_scene_overview_records_manual_all_intent() -> None:
    """All scene selection should clear source focus and store overview intent."""

    service, _input_pane, _output_pane, _output_canvas = _build_service()
    workflow = WorkflowState()
    workflow.active_output_uuid = uuid.uuid4()
    workflow.active_output_source_key = "wf:node"
    workflow.active_output_set_index = 0

    service.output_navigation_session_service.mark_user_navigation("wf", workflow)
    service.output_canvas_focus_service.set_active_output_scene(
        workflow,
        OutputSceneNavigationSelection(
            scene_key=None,
            overview=True,
            source_key=None,
            set_index=1,
            image_id=None,
        ),
    )

    assert workflow.output_focus_mode is OutputFocusMode.MANUAL
    assert workflow.active_output_uuid is None
    assert workflow.active_output_source_key is None
    assert workflow.active_output_set_index == 1
    assert workflow.active_output_scene_key is None
    assert workflow.active_output_scene_overview is True


def test_set_output_compare_state_persists_workflow_compare_state() -> None:
    """Canvas state service should store workflow-owned compare state."""

    service, _input_pane, _output_pane, _output_canvas = _build_service()
    workflow = WorkflowState()
    state = OutputCompareState(
        enabled=True,
        base=OutputCompareSelection(None, 1, "source-a"),
        comparison=OutputCompareSelection("scene-b", 2, "source-b"),
    )

    service.output_canvas_focus_service.set_output_compare_state(workflow, state)

    assert workflow.output_compare_state == state


def test_project_workflow_restores_scene_focus_per_workflow() -> None:
    """Projecting workflows should not leak scene/source focus between them."""

    service, _input_pane, _output_pane, output_canvas = _build_service()
    workflow_a = WorkflowState()
    workflow_b = WorkflowState()
    a_scene1 = uuid.uuid4()
    a_scene2 = uuid.uuid4()
    b_scene1_first = uuid.uuid4()
    b_scene2_first = uuid.uuid4()
    b_scene2_second = uuid.uuid4()
    workflow_a.output_image_uuids = [a_scene1, a_scene2]
    workflow_a.output_focus_mode = OutputFocusMode.MANUAL
    workflow_a.active_output_scene_overview = True
    workflow_b.output_image_uuids = [b_scene1_first, b_scene2_first, b_scene2_second]
    workflow_b.output_focus_mode = OutputFocusMode.MANUAL
    workflow_b.active_output_scene_key = "scene2"
    workflow_b.active_output_scene_overview = False
    workflow_b.active_output_source_key = "wf-b:text"
    workflow_b.active_output_set_index = 0
    scene_records = {
        a_scene1: ImageMeta(
            "wf-a",
            "Text",
            1,
            "",
            "E:/a1.png",
            source_key="wf-a:text",
            scene_key="scene1",
            scene_title="A One",
            scene_order=0,
            scene_count=2,
        ),
        a_scene2: ImageMeta(
            "wf-a",
            "Text",
            1,
            "",
            "E:/a2.png",
            source_key="wf-a:text",
            scene_key="scene2",
            scene_title="A Two",
            scene_order=1,
            scene_count=2,
        ),
        b_scene1_first: ImageMeta(
            "wf-b",
            "Text",
            1,
            "",
            "E:/b1.png",
            source_key="wf-b:text",
            scene_key="scene1",
            scene_title="B One",
            scene_order=0,
            scene_count=2,
        ),
        b_scene2_first: ImageMeta(
            "wf-b",
            "Text",
            1,
            "",
            "E:/b2a.png",
            source_key="wf-b:text",
            scene_key="scene2",
            scene_title="B Two",
            scene_order=1,
            scene_count=2,
        ),
        b_scene2_second: ImageMeta(
            "wf-b",
            "Text",
            2,
            "",
            "E:/b2b.png",
            source_key="wf-b:text",
            scene_key="scene2",
            scene_title="B Two",
            scene_order=1,
            scene_count=2,
        ),
    }
    for image_id, image_meta in scene_records.items():
        _store_image_record(service, image_id, image_meta)
    workflows = {"A": workflow_a, "B": workflow_b}

    service.project_workflow(workflows, "A")
    projection_a_first = output_canvas.sync_calls[-1]
    service.project_workflow(workflows, "B")
    projection_b = output_canvas.sync_calls[-1]
    service.project_workflow(workflows, "A")
    projection_a_second = output_canvas.sync_calls[-1]

    assert projection_a_first.active_scene_overview is True
    assert projection_a_first.active_source_key is None
    assert projection_b.active_scene_overview is False
    assert projection_b.active_scene_key == "scene2"
    assert projection_b.active_source_key == "wf-b:text"
    assert projection_b.active_set_index == 0
    assert projection_a_second.active_scene_overview is True
    assert projection_a_second.active_source_key is None
    assert workflow_a.active_output_source_key is None
    assert workflow_b.active_output_source_key == "wf-b:text"

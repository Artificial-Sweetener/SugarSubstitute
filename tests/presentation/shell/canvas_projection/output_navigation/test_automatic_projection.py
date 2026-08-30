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

"""Characterize automatic output projection and inspection routing."""

import uuid


from substitute.domain.workflow import (
    ImageMeta,
    OutputFocusMode,
    WorkflowState,
)


from ..support.harness import (
    _add_output_image,
    _build_service,
    _store_image_record,
)


def test_add_output_image_promotes_to_all_after_second_scene_is_populated() -> None:
    """Automatic routing should expose All only after two scenes have output."""

    service, _input_pane, _output_pane, output_canvas = _build_service()
    workflow = WorkflowState()
    workflows = {"wf": workflow}

    _add_output_image(
        service,
        workflows,
        origin_workflow_id="wf",
        active_workflow_id="wf",
        image=object(),
        image_meta=ImageMeta(
            workflow_name="Recipe",
            cube_name="Text",
            image_number=1,
            suffix="",
            path="E:/outputs/portrait.png",
            source_key="wf:text",
            source_label="Text",
            scene_run_id="run-1",
            scene_key="portrait",
            scene_title="Portrait",
            scene_order=0,
            scene_count=2,
        ),
    )
    _add_output_image(
        service,
        workflows,
        origin_workflow_id="wf",
        active_workflow_id="wf",
        image=object(),
        image_meta=ImageMeta(
            workflow_name="Recipe",
            cube_name="Text",
            image_number=1,
            suffix="",
            path="E:/outputs/cafe.png",
            source_key="wf:text",
            source_label="Text",
            scene_run_id="run-1",
            scene_key="cafe",
            scene_title="Cafe",
            scene_order=1,
            scene_count=2,
        ),
    )

    first_projection = output_canvas.sync_calls[-2]
    final_projection = output_canvas.sync_calls[-1]

    assert first_projection.active_scene_overview is False
    assert first_projection.scene_count == 1
    assert first_projection.active_set_index == 1
    assert first_projection.active_uuid is not None
    assert final_projection.active_scene_overview is True
    assert final_projection.scene_count == 2
    assert final_projection.active_set_index == 1
    assert final_projection.active_uuid is None
    assert workflow.active_output_uuid is None
    assert workflow.active_output_source_key is None
    assert workflow.active_output_scene_key is None
    assert workflow.active_output_scene_overview is True


def test_begin_output_generation_resets_follow_mode_without_selecting_all() -> None:
    """A new scene run should resume automatic follow without premature overview."""

    service, _input_pane, _output_pane, _output_canvas = _build_service()
    workflow = WorkflowState()
    selected_id = uuid.uuid4()
    workflow.output_focus_mode = OutputFocusMode.MANUAL
    workflow.active_output_uuid = selected_id
    workflow.active_output_source_key = "wf:old"
    workflow.active_output_set_index = 1
    workflow.active_output_scene_key = "old-scene"
    workflow.active_output_scene_overview = False

    state = service.output_navigation_session_service.begin_session(
        {"wf": workflow},
        "wf",
        "run-2",
    )

    assert state is not None
    assert state.focus_mode is OutputFocusMode.AUTOMATIC
    assert state.content_presented is False
    assert workflow.output_focus_mode is OutputFocusMode.MANUAL
    assert workflow.active_output_uuid == selected_id
    assert workflow.active_output_source_key == "wf:old"
    assert workflow.active_output_set_index == 1
    assert workflow.active_output_scene_key == "old-scene"
    assert workflow.active_output_scene_overview is False


def test_project_workflow_keeps_single_populated_scene_on_concrete_output() -> None:
    """One populated scene should remain on its concrete presentable output."""

    service, _input_pane, output_pane, output_canvas = _build_service()
    workflow = WorkflowState()
    workflows = {"wf": workflow}

    _add_output_image(
        service,
        workflows,
        origin_workflow_id="wf",
        active_workflow_id="wf",
        image=object(),
        image_meta=ImageMeta(
            workflow_name="Recipe",
            cube_name="Text",
            image_number=1,
            suffix="",
            path="E:/outputs/portrait.png",
            source_key="wf:text",
            source_label="Text",
            scene_run_id="run-1",
            scene_key="portrait",
            scene_title="Portrait",
            scene_order=0,
            scene_count=2,
        ),
    )

    assert output_canvas.sync_calls[-1].active_scene_overview is False
    assert None not in output_pane.selection_calls


def test_add_output_image_records_automatic_follow_fields() -> None:
    """Automatic output arrival should update follow fields without manual mode."""

    service, _input_pane, _output_pane, _output_canvas = _build_service()
    workflow = WorkflowState()

    _add_output_image(
        service,
        {"wf": workflow},
        origin_workflow_id="wf",
        active_workflow_id="wf",
        image=object(),
        image_meta=ImageMeta(
            "wf",
            "Cube",
            1,
            "",
            "E:/out.png",
            source_key="wf:node",
        ),
    )

    assert workflow.output_focus_mode is OutputFocusMode.AUTOMATIC
    assert workflow.active_output_uuid == workflow.output_image_uuids[-1]
    assert workflow.active_output_source_key == "wf:node"
    assert workflow.active_output_set_index == 1


def test_add_output_image_does_not_overwrite_manual_focus() -> None:
    """Manual output focus should stay sticky when later outputs arrive."""

    service, _input_pane, _output_pane, _output_canvas = _build_service()
    workflow = WorkflowState()
    selected_id = uuid.uuid4()
    workflow.output_image_uuids = [selected_id]
    workflow.output_focus_mode = OutputFocusMode.MANUAL
    workflow.active_output_uuid = selected_id
    workflow.active_output_set_index = 1
    workflow.active_output_source_key = "wf:node"
    _store_image_record(
        service,
        selected_id,
        ImageMeta(
            "wf",
            "Cube",
            1,
            "",
            "E:/one.png",
            source_key="wf:node",
        ),
    )

    _add_output_image(
        service,
        {"wf": workflow},
        origin_workflow_id="wf",
        active_workflow_id="wf",
        image=object(),
        image_meta=ImageMeta(
            "wf",
            "Cube",
            2,
            "",
            "E:/two.png",
            source_key="wf:node",
        ),
    )

    assert workflow.output_focus_mode is OutputFocusMode.MANUAL
    assert workflow.active_output_uuid == selected_id
    assert workflow.active_output_set_index == 1
    assert workflow.active_output_source_key == "wf:node"


def test_update_canvases_automatic_batch_uses_grid_and_keeps_link_group() -> None:
    """Automatic multi-output source should select grid while linking outputs."""
    service, input_pane, output_pane, output_canvas = _build_service()
    workflow = WorkflowState()
    workflow.canvas.input_image_uuid = uuid.uuid4()
    output_a = uuid.uuid4()
    output_b = uuid.uuid4()
    workflow.output_image_uuids = [output_a, output_b]
    workflow.active_output_uuid = None
    _store_image_record(service, output_a, ImageMeta("wf", "cube", 1, "", ""))
    _store_image_record(service, output_b, ImageMeta("wf", "cube", 2, "", ""))

    service.project_workflow({"wf": workflow}, "wf")

    assert input_pane.current_id == workflow.canvas.input_image_uuid
    assert output_pane.current_id is None
    assert workflow.active_output_uuid is None
    assert workflow.active_output_set_index == 0
    assert len(output_pane.linked_groups) == 1
    assert set(output_pane.linked_groups[0].members) == {output_a, output_b}
    projection = output_canvas.sync_calls[-1]
    projected_ids = {
        item.image_id
        for source in projection.sources
        for item in source.images_by_set.values()
    }
    assert projected_ids == {output_a, output_b}
    assert projection.active_uuid is None
    assert projection.active_set_index == 0


def test_output_projection_uses_backend_list_index_not_arrival_order() -> None:
    """Out-of-order finals project into backend-defined set slots."""

    service, _input_pane, _output_pane, output_canvas = _build_service()
    workflow = WorkflowState()
    late_slot = uuid.uuid4()
    first_slot = uuid.uuid4()
    workflow.output_image_uuids = [late_slot, first_slot]
    late_meta = ImageMeta(
        "wf",
        "Cube",
        1,
        "",
        "late.png",
        source_key="wf:save",
        list_index=3,
    )
    first_meta = ImageMeta(
        "wf",
        "Cube",
        2,
        "",
        "first.png",
        source_key="wf:save",
        list_index=0,
    )
    _store_image_record(service, late_slot, late_meta)
    _store_image_record(service, first_slot, first_meta)

    service.project_workflow({"wf": workflow}, "wf")

    source = output_canvas.sync_calls[-1].sources[0]
    assert source.images_by_set[1].image_id == first_slot
    assert source.images_by_set[4].image_id == late_slot


def test_update_canvases_single_output_does_not_create_link_group() -> None:
    """One output image should not create a QPane linked group."""

    service, _input_pane, output_pane, output_canvas = _build_service()
    workflow = WorkflowState()
    output_id = uuid.uuid4()
    workflow.output_image_uuids = [output_id]
    workflow.active_output_uuid = output_id
    _store_image_record(service, output_id, ImageMeta("wf", "cube", 1, "", ""))

    service.project_workflow({"wf": workflow}, "wf")

    assert output_pane.current_id == output_id
    assert output_pane.linked_groups == ()
    projection = output_canvas.sync_calls[-1]
    assert projection.sources[0].images_by_set[1].image_id == output_id
    assert projection.active_uuid == output_id


def test_project_workflow_links_only_projected_output_images() -> None:
    """Linked groups should use projection-backed images, not raw workflow membership."""

    service, _input_pane, output_pane, output_canvas = _build_service()
    workflow = WorkflowState()
    projected_a = uuid.uuid4()
    projected_b = uuid.uuid4()
    unprojected = uuid.uuid4()
    workflow.output_image_uuids = [projected_a, unprojected, projected_b]
    _store_image_record(
        service,
        projected_a,
        ImageMeta("wf", "Cube", 1, "", "E:/a.png", source_key="wf:node"),
    )
    _store_image_record(
        service,
        projected_b,
        ImageMeta("wf", "Cube", 2, "", "E:/b.png", source_key="wf:node"),
    )

    service.project_workflow({"wf": workflow}, "wf")

    assert len(output_pane.linked_groups) == 1
    assert output_pane.linked_groups[0].members == (projected_a, projected_b)
    projected_ids = {
        item.image_id
        for source in output_canvas.sync_calls[-1].sources
        for item in source.images_by_set.values()
    }
    assert projected_ids == {projected_a, projected_b}
    assert unprojected not in projected_ids


def test_project_workflow_skips_reselecting_current_output_uuid() -> None:
    """Projection should not restart QPane navigation for the current output UUID."""

    service, _input_pane, output_pane, _output_canvas = _build_service()
    workflow = WorkflowState()
    output_id = uuid.uuid4()
    workflow.output_image_uuids = [output_id]
    workflow.active_output_uuid = output_id
    output_pane.current_id = output_id
    _store_image_record(service, output_id, ImageMeta("wf", "cube", 1, "", ""))

    service.project_workflow({"wf": workflow}, "wf")

    assert output_pane.selection_calls == []
    assert output_pane.current_id == output_id

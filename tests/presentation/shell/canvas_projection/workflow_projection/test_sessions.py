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

"""Characterize canvas projection workflow session contracts."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from substitute.application.workflows.output_canvas_session import OutputCanvasSession
from substitute.domain.workflow import (
    CanvasKind,
    ImageMeta,
    OutputFocusMode,
    WorkflowState,
)


from ..support.harness import (
    _build_service,
    _store_image_record,
)


def test_project_workflow_binds_input_and_output_canvas_sessions() -> None:
    """Workflow projection binds shared Input and Output session identities."""

    service, _input_pane, _output_pane, output_canvas = _build_service()
    workflow = WorkflowState()
    input_id = uuid.uuid4()
    output_id = uuid.uuid4()
    workflow.canvas.input_image_uuid = input_id
    workflow.canvas.bind_image("wf:load", input_id)
    workflow.output_image_uuids = [output_id]
    workflow.active_output_uuid = output_id
    _store_image_record(
        service,
        output_id,
        ImageMeta(
            workflow_name="wf",
            cube_name="Save",
            image_number=1,
            suffix="",
            path="E:/output.png",
            source_key="wf:save",
            node_id="save-node",
            generation_run_id="run-1",
            prompt_id="prompt-1",
            client_id="client-1",
            list_index=0,
        ),
    )

    service.project_workflow({"wf": workflow}, "wf")

    input_session = service.canvas_session_boundary.current_session(CanvasKind.INPUT)
    route_session = service.canvas_session_boundary.current_session(CanvasKind.OUTPUT)
    output_session = output_canvas.sync_session_calls[-1]
    assert input_session is not None
    assert input_session.workflow_id.value == "wf"
    assert input_session.active_route.primary_image_id == input_id
    assert input_session.active_route.route_kind == "input_image"
    assert isinstance(output_session, OutputCanvasSession)
    assert route_session == output_session.session
    assert output_session.workflow_id.value == "wf"
    assert output_session.active_route.primary_image_id == output_id
    assert output_session.active_route.route_key == (
        f"image:{output_id};scene:;source:wf:save;set:1"
    )
    assert output_session.projection is output_canvas.sync_calls[-1]
    assert output_session.allowed_image_ids == frozenset({output_id})
    assert output_session.allowed_source_keys == frozenset({"wf:save"})
    assert output_session.generation_identity is not None
    assert output_session.generation_identity.generation_run_id == "run-1"
    assert output_session.generation_identity.prompt_id == "prompt-1"
    assert output_session.generation_identity.client_id == "client-1"


@pytest.mark.parametrize(
    ("generation_run_id", "prompt_id", "client_id"),
    (
        ("", "prompt-1", "client-1"),
        ("run-1", "", "client-1"),
        ("run-1", "prompt-1", ""),
    ),
)
def test_project_workflow_does_not_bind_partial_output_generation_identity(
    generation_run_id: str,
    prompt_id: str,
    client_id: str,
) -> None:
    """Workflow projection binds Output generation identity only when complete."""

    service, _input_pane, _output_pane, output_canvas = _build_service()
    workflow = WorkflowState()
    output_id = uuid.uuid4()
    workflow.output_image_uuids = [output_id]
    workflow.active_output_uuid = output_id
    _store_image_record(
        service,
        output_id,
        ImageMeta(
            workflow_name="wf",
            cube_name="Save",
            image_number=1,
            suffix="",
            path="E:/output.png",
            source_key="wf:save",
            generation_run_id=generation_run_id,
            prompt_id=prompt_id,
            client_id=client_id,
        ),
    )

    service.project_workflow({"wf": workflow}, "wf")

    output_session = output_canvas.sync_session_calls[-1]
    assert isinstance(output_session, OutputCanvasSession)
    assert output_session.generation_identity is None


def test_unchanged_project_workflow_keeps_existing_session_token_current() -> None:
    """An unchanged projection should not invalidate active display authority."""

    service, _input_pane, _output_pane, _output_canvas = _build_service()
    workflow = WorkflowState()
    output_id = uuid.uuid4()
    workflow.output_image_uuids = [output_id]
    workflow.active_output_uuid = output_id
    _store_image_record(
        service,
        output_id,
        ImageMeta(
            "wf",
            "Save",
            1,
            "",
            "E:/output.png",
            source_key="wf:save",
        ),
    )

    service.project_workflow({"wf": workflow}, "wf")
    first_output_session = _output_canvas.sync_session_calls[-1]
    assert isinstance(first_output_session, OutputCanvasSession)

    service.project_workflow({"wf": workflow}, "wf")
    authorization = service.canvas_session_boundary.authorize_display_mutation(
        first_output_session.token(),
    )

    assert authorization.accepted is True
    assert authorization.rejection_reason is None


def test_project_workflow_clears_foreign_output_image_when_switching_to_grid() -> None:
    """Inactive Output images stay cached but must not stay visible."""

    service, _input_pane, output_pane, output_canvas = _build_service()
    workflow_a = WorkflowState()
    workflow_b = WorkflowState()
    output_a = uuid.uuid4()
    output_b1 = uuid.uuid4()
    output_b2 = uuid.uuid4()
    workflow_a.output_image_uuids = [output_a]
    workflow_a.active_output_uuid = output_a
    workflow_b.output_image_uuids = [output_b1, output_b2]
    workflow_b.active_output_uuid = None
    output_pane.images[output_a] = ("output-a", Path("output-a.png"))
    output_pane.images[output_b1] = ("output-b1", Path("output-b1.png"))
    output_pane.images[output_b2] = ("output-b2", Path("output-b2.png"))
    _store_image_record(
        service,
        output_a,
        ImageMeta(
            "A",
            "Cube",
            1,
            "",
            "output-a.png",
            source_key="A:save",
        ),
    )
    _store_image_record(
        service,
        output_b1,
        ImageMeta(
            "B",
            "Cube",
            1,
            "",
            "output-b1.png",
            source_key="B:save",
        ),
    )
    _store_image_record(
        service,
        output_b2,
        ImageMeta(
            "B",
            "Cube",
            2,
            "",
            "output-b2.png",
            source_key="B:save",
        ),
    )

    service.project_workflow({"A": workflow_a, "B": workflow_b}, "A")
    service.project_workflow({"A": workflow_a, "B": workflow_b}, "B")

    assert set(output_pane.images) == {output_a, output_b1, output_b2}
    assert output_pane.selection_calls[-1] is None
    assert output_pane.current_id is None
    assert output_canvas.sync_calls[-1].active_uuid is None
    assert output_canvas.sync_calls[-1].active_set_index == 0


def test_project_workflow_hydrates_output_canvas_from_image_registry() -> None:
    """Projection should hydrate visible output caches from registry records."""

    service, _input_pane, _output_pane, output_canvas = _build_service()
    workflow = WorkflowState()
    image_id = uuid.uuid4()
    image = object()
    meta = ImageMeta("wf", "Cube", 1, "", "", source_key="wf:cube")
    workflow.output_image_uuids.append(image_id)
    _store_image_record(service, image_id, meta, payload=image)

    service.project_workflow({"wf": workflow}, "wf")

    workflow_id, image_ids = output_canvas.prepare_calls[-1]
    assert workflow_id == "wf"
    assert image_ids == (image_id,)
    assert service.image_registry.payload_for(image_id) is image
    assert service.image_registry.metadata_for(image_id) is meta
    assert output_canvas.sync_calls[-1].sources


def test_project_workflow_warms_all_scene_overview_images() -> None:
    """Scene overview projection should warm every scene representative image."""

    service, _input_pane, output_pane, output_canvas = _build_service()
    workflow = WorkflowState()
    image_ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
    workflow.output_image_uuids = list(image_ids)
    workflow.active_output_scene_overview = True
    workflow.output_focus_mode = OutputFocusMode.MANUAL
    payloads = {image_id: object() for image_id in image_ids}
    for index, image_id in enumerate(image_ids):
        _store_image_record(
            service,
            image_id,
            ImageMeta(
                "Scene Test",
                "Text",
                1,
                "",
                f"E:/outputs/scene-{index}.png",
                source_key="wf:text",
                source_label="Text",
                scene_run_id="scene-run",
                scene_key=f"scene-{index}",
                scene_title=f"Scene {index}",
                scene_order=index,
                scene_count=len(image_ids),
                list_index=0,
                generation_run_id="run",
                prompt_id="prompt",
                client_id="client",
                node_id="node",
            ),
            payload=payloads[image_id],
        )

    service.project_workflow({"wf": workflow}, "wf")

    warmed_ids = tuple(image_id for image_id, _image, _path in output_pane.add_calls)
    assert set(warmed_ids) == set(image_ids)
    assert len(warmed_ids) == len(image_ids)
    assert set(output_pane.images) == set(image_ids)
    assert output_canvas.sync_calls[-1].active_scene_overview is True
    assert [
        scene.primary_image_id for scene in output_canvas.sync_calls[-1].scene_groups
    ] == image_ids


def test_project_workflow_clears_transient_previews_when_workflow_changes() -> None:
    """Application session transition should retire previews before binding output."""

    service, _input_pane, _output_pane, output_canvas = _build_service()
    workflow_a = WorkflowState()
    workflow_b = WorkflowState()
    image_a = uuid.uuid4()
    image_b = uuid.uuid4()
    payload_a = object()
    payload_b = object()
    meta_a = ImageMeta("wf-a", "Cube", 1, "", "", source_key="A:cube")
    meta_b = ImageMeta("wf-b", "Cube", 1, "", "", source_key="B:cube")
    workflow_a.output_image_uuids.append(image_a)
    workflow_b.output_image_uuids.append(image_b)
    _store_image_record(service, image_a, meta_a, payload=payload_a)
    _store_image_record(service, image_b, meta_b, payload=payload_b)

    service.project_workflow({"A": workflow_a, "B": workflow_b}, "A")
    output_canvas.events.clear()

    service.project_workflow({"A": workflow_a, "B": workflow_b}, "B")

    assert output_canvas.clear_preview_calls == [None, None]
    assert output_canvas.events[0] == ("clear_previews", None)
    assert output_canvas.events[1] == ("bind", "B")
    assert output_canvas.prepare_calls[-1][1] == (image_b,)
    assert service.image_registry.payload_for(image_b) is payload_b


def test_project_workflow_keeps_transient_previews_when_reprojecting_same_workflow() -> (
    None
):
    """Same-workflow duplicate projection must not replay stale visible routes."""

    service, _input_pane, _output_pane, output_canvas = _build_service()
    workflow = WorkflowState()
    image_id = uuid.uuid4()
    payload = object()
    meta = ImageMeta("wf", "Cube", 1, "", "", source_key="wf:cube")
    workflow.output_image_uuids.append(image_id)
    _store_image_record(service, image_id, meta, payload=payload)

    service.project_workflow({"wf": workflow}, "wf")
    output_canvas.clear_preview_calls.clear()
    output_canvas.events.clear()
    output_canvas.prepare_calls.clear()
    output_canvas.sync_calls.clear()

    service.project_workflow({"wf": workflow}, "wf")

    assert output_canvas.clear_preview_calls == []
    assert output_canvas.events == []
    assert output_canvas.prepare_calls == []
    assert output_canvas.sync_calls == []


def test_project_workflow_resyncs_same_workflow_after_metadata_changes() -> None:
    """Same-workflow projection should resync when display metadata changes."""

    service, _input_pane, _output_pane, output_canvas = _build_service()
    workflow = WorkflowState()
    image_id = uuid.uuid4()
    payload = object()
    meta = ImageMeta("wf", "Cube", 1, "", "", source_key="wf:cube")
    workflow.output_image_uuids.append(image_id)
    _store_image_record(service, image_id, meta, payload=payload)

    service.project_workflow({"wf": workflow}, "wf")
    output_canvas.events.clear()
    output_canvas.prepare_calls.clear()
    output_canvas.sync_calls.clear()

    meta.cube_execution_duration_ms = 42.5
    service.project_workflow({"wf": workflow}, "wf")

    assert output_canvas.events[0] == ("bind", "wf")
    assert output_canvas.prepare_calls[-1][1] == (image_id,)
    assert service.image_registry.payload_for(image_id) is payload
    assert output_canvas.sync_calls


def test_repeated_output_projection_skips_existing_identical_payload() -> None:
    """Projection catalog warming should not re-add unchanged output payloads."""

    service, _input_pane, output_pane, _output_canvas = _build_service()
    workflow = WorkflowState()
    image = object()
    image_meta = ImageMeta("wf", "Cube", 1, "", "E:/out.png")
    result = service.output_canvas_state_service.register_output_image(
        {"wf": workflow},
        origin_workflow_id="wf",
        active_workflow_id="wf",
        image=image,
        image_meta=image_meta,
    )

    service.project_output({"wf": workflow}, "wf")
    service.project_output({"wf": workflow}, "wf")

    assert output_pane.add_calls == [(result.image_id, image, Path("E:/out.png"))]


def test_repeated_output_projection_does_not_reapply_visible_route() -> None:
    """Unchanged Output projection must not replay stale visible routes."""

    service, _input_pane, _output_pane, output_canvas = _build_service()
    workflow = WorkflowState()
    image = object()
    image_meta = ImageMeta("wf", "Cube", 1, "", "E:/out.png", source_key="wf:cube")
    service.output_canvas_state_service.register_output_image(
        {"wf": workflow},
        origin_workflow_id="wf",
        active_workflow_id="wf",
        image=image,
        image_meta=image_meta,
    )

    service.project_output({"wf": workflow}, "wf")
    first_session = output_canvas.sync_session_calls[-1]
    output_canvas.sync_session_calls.clear()
    output_canvas.prepare_calls.clear()
    service.project_output({"wf": workflow}, "wf")
    second_session = service.canvas_session_boundary.current_session(CanvasKind.OUTPUT)

    assert output_canvas.sync_session_calls == []
    assert output_canvas.prepare_calls == []
    assert second_session is not None
    assert second_session.revision.value == first_session.revision.value

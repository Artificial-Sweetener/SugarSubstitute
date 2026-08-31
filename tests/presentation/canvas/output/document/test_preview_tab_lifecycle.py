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

"""Verify real Output source tabs across preview and final lifecycle changes."""

from __future__ import annotations

from uuid import UUID, uuid4

from substitute.application.workflows.canvas_route_projector_port import (
    create_canvas_session_boundary,
)
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasProjection,
    OutputCanvasSourceGroup,
    build_output_canvas_projection,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewRegistry,
)
from substitute.application.workflows.output_canvas_state_service import (
    OutputPreviewCloseIdentity,
)
from substitute.domain.workflow import ImageMeta, WorkflowState
from substitute.presentation.canvas.output.output_canvas_view import OutputCanvas
from cutecanvas import ExecutionRuntime
from tests.application.workflows.output_canvas_projection.support import build_meta
from tests.support.qt.lifecycle import destroy_qt_object

from .support import _app, _image, _live_preview_event, _session


def test_real_source_tabs_merge_restored_and_current_run_cube_outputs(
    execution_runtime: ExecutionRuntime,
) -> None:
    """Render four cube tabs from the six finals in the reported duplicate strip."""

    _app()
    workflow = WorkflowState()
    image_ids = tuple(uuid4() for _index in range(6))
    workflow.output_image_uuids = list(image_ids)
    metadata = _duplicate_strip_metadata(image_ids)
    projection = build_output_canvas_projection(workflow, metadata)
    boundary = create_canvas_session_boundary()
    canvas = OutputCanvas(
        execution_runtime=execution_runtime,
        preview_registry=OutputPreviewRegistry(),
        route_session_boundary=boundary,
    )
    try:
        for image_id in image_ids:
            assert canvas.document.admit_image(image_id, _image("red"))
        canvas.bind_projection_session(_session(boundary, projection))

        assert tuple(canvas.tabbar.items) == (
            "cube:Text to Image",
            "cube:Diffusion Upscale",
            "cube:Automask Detailer",
            "cube:Automask Detailer 2",
        )
        assert tuple(item.text() for item in canvas.tabbar.items.values()) == (
            "Text to Image",
            "Diffusion Upscale",
            "Automask Detailer",
            "Automask Detailer 2",
        )
    finally:
        canvas.close()
        destroy_qt_object(canvas)


def test_matching_final_replaces_preview_without_adding_a_second_tab(
    execution_runtime: ExecutionRuntime,
) -> None:
    """Retire a source placeholder when its matching set-one final arrives."""

    _app()
    boundary = create_canvas_session_boundary()
    registry = OutputPreviewRegistry()
    canvas = OutputCanvas(
        execution_runtime=execution_runtime,
        preview_registry=registry,
        route_session_boundary=boundary,
    )
    source_key = "cube:Diffusion Upscale"
    try:
        empty_session = _session(
            boundary,
            OutputCanvasProjection(
                sources=(),
                active_source_key=None,
                active_set_index=1,
                active_uuid=None,
                set_count=0,
            ),
        )
        canvas.bind_projection_session(empty_session)
        acceptance = registry.accept_preview(
            _live_preview_event(_image("green"), source_key=source_key),
            session=empty_session,
            active_workflow_id="workflow",
            authorize_preview=lambda _identity: True,
            is_valid_source_placeholder=lambda _identity: True,
        )
        assert acceptance.accepted
        canvas.apply_preview_acceptance(acceptance)
        preview_id = acceptance.lanes[0].preview_id
        assert tuple(canvas.tabbar.items) == (source_key,)

        final_id = uuid4()
        final_meta = ImageMeta(
            workflow_name="workflow",
            cube_name="Diffusion Upscale",
            image_number=1,
            suffix="",
            path="E:/outputs/final.png",
            source_key=source_key,
            source_label="Diffusion Upscale",
            generation_run_id="run",
            prompt_id="prompt",
            client_id="client",
            node_id="preview-node",
            list_index=0,
        )
        assert canvas.document.admit_image(final_id, _image("blue"))
        canvas.close_final_output_preview_lane(
            OutputPreviewCloseIdentity(
                workflow_id="workflow",
                image_id=final_id,
                source_key=source_key,
                source_label="Diffusion Upscale",
                generation_run_id="run",
                prompt_id="prompt",
                client_id="client",
                node_id="preview-node",
                list_index=0,
                scene_run_id=None,
                scene_key=None,
                scene_title=None,
                scene_order=None,
                scene_count=None,
            )
        )
        final_projection = OutputCanvasProjection(
            sources=(
                OutputCanvasSourceGroup(
                    source_key=source_key,
                    label="Diffusion Upscale",
                    images_by_set={
                        1: OutputCanvasImageItem(
                            image_id=final_id,
                            image_meta=final_meta,
                            set_index=1,
                        )
                    },
                ),
            ),
            active_source_key=source_key,
            active_set_index=1,
            active_uuid=final_id,
            set_count=1,
        )
        canvas.bind_projection_session(_session(boundary, final_projection))

        assert registry.lane_for_id(preview_id) is None
        assert canvas.document.composition_id_for(preview_id) is None
        assert tuple(canvas.tabbar.items) == (source_key,)
        final_composition = canvas.document.composition_id_for(final_id)
        assert final_composition is not None
        assert canvas.workspace.session.presentation.target_ids == (final_composition,)
    finally:
        canvas.close()
        destroy_qt_object(canvas)


def _duplicate_strip_metadata(
    image_ids: tuple[UUID, ...],
) -> dict[UUID, ImageMeta]:
    """Build the old/new final identities that produced six visible source tabs."""

    labels = (
        "Text to Image",
        "Diffusion Upscale",
        "Text to Image",
        "Diffusion Upscale",
        "Automask Detailer",
        "Automask Detailer 2",
    )
    node_ids = ("8", "17", "28", "31", "34", "36")
    run_names = (
        "workflow-old",
        "workflow-old",
        "workflow-new",
        "workflow-new",
        "workflow-new",
        "workflow-new",
    )
    return {
        image_id: build_meta(
            label,
            source_key=f"{run_name}:{node_id}",
            node_id=node_id,
            list_index=0,
        )
        for image_id, label, node_id, run_name in zip(
            image_ids,
            labels,
            node_ids,
            run_names,
            strict=True,
        )
    }

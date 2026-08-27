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

"""Verify Output document identity, session, preview, and lifetime contracts."""

from __future__ import annotations

from uuid import uuid4
from PySide6.QtGui import (
    QColor,
)
from substitute.application.workflows.canvas_route_projector_port import (
    create_canvas_session_boundary,
)
from substitute.application.workflows.output_detail_inspection import (
    OutputDetailInspectionGroup,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewAcceptance,
    OutputPreviewRegistry,
)
from substitute.presentation.canvas.output.output_canvas_view import OutputCanvas
from substitute.presentation.canvas.output.output_document import OutputCanvasDocument
from cutecanvas import ExecutionRuntime
from tests.support.qt.lifecycle import destroy_qt_object

from .rendering_support import _wait_for_rendered_color
from .support import (
    _image,
    _app,
    _projection,
    _session,
    _source_preview_lane,
    _live_preview_event,
    _scene_preview_lane,
)


def test_output_document_owns_locked_compositions_and_presentations(
    execution_runtime: ExecutionRuntime,
) -> None:
    """Map application images to read-only compositions across Output views."""

    _app()
    document = OutputCanvasDocument(execution_runtime=execution_runtime)
    first_id = uuid4()
    second_id = uuid4()
    first_image = _image("red")
    second_image = _image("blue")

    try:
        assert document.admit_image(first_id, first_image)
        assert document.admit_image(second_id, second_image)
        assert not document.admit_image(first_id, first_image)

        first_composition = document.composition_id_for(first_id)
        second_composition = document.composition_id_for(second_id)
        assert first_composition is not None
        assert second_composition is not None

        document.present_single(first_id)
        single_presentation = document.workspace.session.presentation
        assert single_presentation.target_ids == (first_composition,)
        assert document.workspace.session.inspection.groups() == ()

        document.present_grid((first_id, second_id))
        grid_presentation = document.workspace.session.presentation
        assert grid_presentation.target_ids == (
            first_composition,
            second_composition,
        )
        assert document.workspace.session.inspection.groups() == ()

        document.present_comparison(
            first_id,
            second_id,
            split_position=0.25,
            orientation="horizontal",
        )
        comparison = document.workspace.session.presentation.comparison
        assert comparison is not None
        assert comparison.primary_id == first_composition
        assert comparison.secondary_id == second_composition
        assert comparison.split_position == 0.25
        assert comparison.orientation.value == "horizontal"
        assert document.workspace.session.inspection.groups() == ()

        snapshot = document.document.snapshot()
        first_entry = snapshot.compositions[first_composition]
        assert first_entry.policy.removable
        assert first_entry.layers[0].interaction.selectable is False
        assert first_entry.layers[0].interaction.movable is False
        assert first_entry.layers[0].interaction.pixel_editable is False
        assert first_entry.layers[0].interaction.reorderable is False
        assert first_entry.layers[0].interaction.removable is False
    finally:
        document.close()


def test_output_document_replaces_and_retires_content_without_stale_identity(
    execution_runtime: ExecutionRuntime,
) -> None:
    """Replace changed pixels and retire only the corresponding composition."""

    _app()
    document = OutputCanvasDocument(execution_runtime=execution_runtime)
    image_id = uuid4()

    try:
        assert document.admit_image(image_id, _image("red"))
        original_composition = document.composition_id_for(image_id)
        assert original_composition is not None
        reference = document.content_reference_for(image_id)
        assert reference is not None
        assert document.image_id_for_content_reference(reference) == image_id

        assert document.admit_image(image_id, _image("blue"))
        replacement_composition = document.composition_id_for(image_id)
        assert replacement_composition is not None
        assert replacement_composition != original_composition
        assert document.image_id_for_content_reference(reference) is None

        assert document.retire_image(image_id)
        assert document.composition_id_for(image_id) is None
        assert not document.retire_image(image_id)
    finally:
        document.close()
        destroy_qt_object(document)


def test_output_document_retains_inactive_workflow_detail_groups(
    execution_runtime: ExecutionRuntime,
) -> None:
    """Keep independent workflow inspection state while another workflow is active."""

    _app()
    document = OutputCanvasDocument(execution_runtime=execution_runtime)
    image_ids = tuple(uuid4() for _index in range(4))
    try:
        for image_id, color in zip(
            image_ids,
            ("red", "blue", "green", "yellow"),
            strict=True,
        ):
            assert document.admit_image(image_id, _image(color))
        first_group_id = uuid4()
        second_group_id = uuid4()
        document.set_detail_inspection_groups(
            workflow_id="first",
            groups=(
                OutputDetailInspectionGroup(
                    first_group_id,
                    "first",
                    "scene",
                    1,
                    image_ids[:2],
                ),
            ),
        )
        document.set_detail_inspection_groups(
            workflow_id="second",
            groups=(
                OutputDetailInspectionGroup(
                    second_group_id,
                    "second",
                    "scene",
                    1,
                    image_ids[2:],
                ),
            ),
        )

        groups = document.workspace.session.inspection.groups()
        assert tuple(group.group_id for group in groups) == (
            first_group_id,
            second_group_id,
        )
        assert set(groups[0].members).isdisjoint(groups[1].members)
    finally:
        document.close()
        destroy_qt_object(document)


def test_output_document_preview_admission_preserves_source_and_scene_routes(
    execution_runtime: ExecutionRuntime,
) -> None:
    """Represent accepted live previews as locked document compositions."""

    _app()
    final_id = uuid4()
    source_preview_id = uuid4()
    scene_preview_id = uuid4()
    projection = _projection(final_id, uuid4())
    boundary = create_canvas_session_boundary()
    registry = OutputPreviewRegistry()
    canvas = OutputCanvas(
        execution_runtime=execution_runtime,
        preview_registry=registry,
        route_session_boundary=boundary,
    )

    try:
        assert canvas.document.admit_image(final_id, _image("red"))
        session = _session(boundary, projection)
        canvas.bind_projection_session(session)
        source_lane = _source_preview_lane(source_preview_id, session)
        registry.store_accepted_lane(source_lane)

        canvas.apply_preview_acceptance(
            OutputPreviewAcceptance(accepted=True, lanes=(source_lane,))
        )

        source_composition = canvas.document.composition_id_for(source_preview_id)
        assert source_composition is not None
        assert canvas.workspace.session.presentation.target_ids == (source_composition,)

        scene_lane = _scene_preview_lane(scene_preview_id, session)
        registry.store_accepted_lane(scene_lane)
        canvas.apply_preview_acceptance(
            OutputPreviewAcceptance(accepted=True, lanes=(scene_lane,))
        )

        scene_composition = canvas.document.composition_id_for(scene_preview_id)
        assert scene_composition is not None
        assert canvas.active_scene_overview is True
        assert scene_composition in canvas.workspace.session.presentation.target_ids
    finally:
        canvas.close()
        destroy_qt_object(canvas)


def test_comfy_preview_event_reaches_the_visible_output_document(
    execution_runtime: ExecutionRuntime,
) -> None:
    """Route an authorized transient Comfy preview into the real active Output view."""

    app = _app()
    final_id = uuid4()
    boundary = create_canvas_session_boundary()
    registry = OutputPreviewRegistry()
    canvas = OutputCanvas(
        execution_runtime=execution_runtime,
        preview_registry=registry,
        route_session_boundary=boundary,
    )
    try:
        canvas.resize(640, 480)
        canvas.show()
        assert canvas.document.admit_image(final_id, _image("red"))
        session = _session(boundary, _projection(final_id, uuid4()))
        canvas.bind_projection_session(session)

        first_event = _live_preview_event(_image("green"))
        first_acceptance = registry.accept_preview(
            first_event,
            session=session,
            active_workflow_id="workflow",
            authorize_preview=lambda _identity: True,
        )
        assert first_acceptance.accepted
        canvas.apply_preview_acceptance(first_acceptance)
        preview_id = first_acceptance.lanes[0].preview_id
        first_target_id = canvas.document.composition_id_for(preview_id)
        assert first_target_id is not None
        first_target = canvas.workspace.canvasFor(first_target_id)
        assert first_target is not None
        assert _wait_for_rendered_color(app, first_target, QColor("green"))

        replacement_event = _live_preview_event(_image("blue"))
        replacement_acceptance = registry.accept_preview(
            replacement_event,
            session=session,
            active_workflow_id="workflow",
            authorize_preview=lambda _identity: True,
        )
        assert replacement_acceptance.accepted
        assert replacement_acceptance.lanes[0].preview_id == preview_id
        canvas.apply_preview_acceptance(replacement_acceptance)
        replacement_target_id = canvas.document.composition_id_for(preview_id)
        assert replacement_target_id is not None
        replacement_target = canvas.workspace.canvasFor(replacement_target_id)
        assert replacement_target is not None
        assert _wait_for_rendered_color(app, replacement_target, QColor("blue"))
    finally:
        canvas.close()
        destroy_qt_object(canvas)


def test_output_document_survives_non_destructive_widget_close(
    execution_runtime: ExecutionRuntime,
) -> None:
    """Keep the application-lifetime Output document warm across widget closes."""

    _app()
    canvas = OutputCanvas(
        execution_runtime=execution_runtime,
        preview_registry=OutputPreviewRegistry(),
        route_session_boundary=create_canvas_session_boundary(),
    )
    image_id = uuid4()

    try:
        canvas.close()

        assert canvas.document.admit_image(image_id, _image("purple"))
    finally:
        destroy_qt_object(canvas)

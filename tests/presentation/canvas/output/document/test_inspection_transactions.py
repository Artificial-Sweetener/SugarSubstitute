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

"""Verify transactional Output inspection-group publication."""

from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

import pytest
from cutecanvas import ExecutionRuntime

from substitute.application.workflows.canvas_route_projector_port import (
    create_canvas_session_boundary,
)
from substitute.application.workflows.output_canvas_session import (
    bind_output_canvas_session,
)
from substitute.application.workflows.output_detail_inspection import (
    OutputDetailInspectionGroup,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewRegistry,
)
from substitute.presentation.canvas.output.output_canvas_view import OutputCanvas
from substitute.presentation.canvas.output.output_document import OutputCanvasDocument
from tests.presentation.canvas.output.document.support import (
    _app,
    _image,
    _projection,
    _session,
)
from tests.support.qt.lifecycle import destroy_qt_object


def test_output_document_rejects_overlap_without_mutating_retained_groups(
    execution_runtime: ExecutionRuntime,
) -> None:
    """Reject a poisoned group proposal while preserving the prior projection."""

    _app()
    document = OutputCanvasDocument(execution_runtime=execution_runtime)
    image_ids = (uuid4(), uuid4())
    original_group_id = uuid4()
    try:
        for image_id, color in zip(image_ids, ("red", "blue"), strict=True):
            assert document.admit_image(image_id, _image(color))
        document.set_detail_inspection_groups(
            workflow_id="first",
            groups=(
                OutputDetailInspectionGroup(
                    original_group_id,
                    "first",
                    "scene",
                    1,
                    image_ids,
                ),
            ),
        )

        with pytest.raises(
            ValueError,
            match="inspection targets cannot belong to multiple groups",
        ):
            document.set_detail_inspection_groups(
                workflow_id="second",
                groups=(
                    OutputDetailInspectionGroup(
                        uuid4(),
                        "second",
                        "scene",
                        1,
                        image_ids,
                    ),
                ),
            )

        groups = document.workspace.session.inspection.groups()
        assert tuple(group.group_id for group in groups) == (original_group_id,)
        document.discard_workflow_detail_groups("first")
        assert document.workspace.session.inspection.groups() == ()
    finally:
        document.close()
        destroy_qt_object(document)


def test_output_canvas_preflights_groups_before_session_mutation(
    execution_runtime: ExecutionRuntime,
) -> None:
    """A poisoned projection must leave the mounted workflow fully usable."""

    _app()
    boundary = create_canvas_session_boundary()
    canvas = OutputCanvas(
        execution_runtime=execution_runtime,
        preview_registry=OutputPreviewRegistry(),
        route_session_boundary=boundary,
    )
    image_ids = (uuid4(), uuid4())
    projection = _projection(*image_ids)
    original_group_id = uuid4()
    try:
        for image_id, color in zip(image_ids, ("red", "blue"), strict=True):
            assert canvas.document.admit_image(image_id, _image(color))
        original = replace(
            _session(boundary, projection),
            detail_inspection_groups=(
                OutputDetailInspectionGroup(
                    original_group_id,
                    "workflow",
                    "scene",
                    1,
                    image_ids,
                ),
            ),
        )
        canvas.bind_projection_session(original)
        previous_selection = (
            canvas.active_source_key,
            canvas.active_set_index,
            canvas.active_scene_key,
        )
        conflicting = bind_output_canvas_session(
            boundary,
            workflow_id="other",
            projection=projection,
            image_metadata_lookup={
                item.image_id: item.image_meta
                for source in projection.sources
                for item in source.images_by_set.values()
            },
        )
        conflicting = replace(
            conflicting,
            detail_inspection_groups=(
                OutputDetailInspectionGroup(
                    uuid4(),
                    "other",
                    "scene",
                    1,
                    image_ids,
                ),
            ),
        )

        with pytest.raises(
            ValueError,
            match="inspection targets cannot belong to multiple groups",
        ):
            canvas.bind_projection_session(conflicting)

        assert (
            canvas.active_source_key,
            canvas.active_set_index,
            canvas.active_scene_key,
        ) == previous_selection
        groups = canvas.workspace.session.inspection.groups()
        assert tuple(group.group_id for group in groups) == (original_group_id,)
        canvas.discard_workflow_detail_groups("workflow")
        assert canvas.workspace.session.inspection.groups() == ()
    finally:
        canvas.close()
        destroy_qt_object(canvas)

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

"""Verify Output projection focus persistence and fallback semantics."""

from __future__ import annotations

from uuid import uuid4

from substitute.application.workflows import build_output_canvas_projection
from substitute.domain.workflow import OutputFocusMode, WorkflowState


from tests.application.workflows.output_canvas_projection.support import build_meta


def test_projection_falls_back_when_active_uuid_is_stale() -> None:
    """A stale active UUID should select the first available source item."""

    workflow = WorkflowState()
    first_id = uuid4()
    workflow.output_image_uuids = [first_id]
    workflow.active_output_uuid = uuid4()

    projection = build_output_canvas_projection(
        workflow,
        {first_id: build_meta("Text to Image", source_key="wf:text")},
    )

    assert projection.active_source_key == "wf:text"
    assert projection.active_set_index == 1
    assert projection.active_uuid == first_id


def test_projection_automatic_batch_activates_grid() -> None:
    """Automatic multi-output focus should select grid set zero."""

    workflow = WorkflowState()
    ids = [uuid4(), uuid4(), uuid4()]
    workflow.output_image_uuids = ids
    workflow.active_output_uuid = ids[-1]
    workflow.active_output_source_key = "wf:text"

    projection = build_output_canvas_projection(
        workflow,
        {
            ids[0]: build_meta("Text to Image", source_key="wf:text", image_number=1),
            ids[1]: build_meta("Text to Image", source_key="wf:text", image_number=2),
            ids[2]: build_meta("Text to Image", source_key="wf:text", image_number=3),
        },
    )

    assert projection.active_source_key == "wf:text"
    assert projection.active_set_index == 0
    assert projection.active_uuid is None


def test_projection_manual_concrete_selection_stays_sticky() -> None:
    """Manual output focus should keep the selected concrete set."""

    workflow = WorkflowState()
    ids = [uuid4(), uuid4(), uuid4()]
    workflow.output_image_uuids = ids
    workflow.output_focus_mode = OutputFocusMode.MANUAL
    workflow.active_output_uuid = ids[1]
    workflow.active_output_set_index = 2
    workflow.active_output_source_key = "wf:text"

    projection = build_output_canvas_projection(
        workflow,
        {
            ids[0]: build_meta("Text to Image", source_key="wf:text", image_number=1),
            ids[1]: build_meta("Text to Image", source_key="wf:text", image_number=2),
            ids[2]: build_meta("Text to Image", source_key="wf:text", image_number=3),
        },
    )

    assert projection.active_source_key == "wf:text"
    assert projection.active_set_index == 2
    assert projection.active_uuid == ids[1]


def test_projection_manual_grid_selection_stays_sticky() -> None:
    """Manual grid focus should keep set zero when the grid remains available."""

    workflow = WorkflowState()
    ids = [uuid4(), uuid4(), uuid4()]
    workflow.output_image_uuids = ids
    workflow.output_focus_mode = OutputFocusMode.MANUAL
    workflow.active_output_uuid = None
    workflow.active_output_set_index = 0
    workflow.active_output_source_key = "wf:text"

    projection = build_output_canvas_projection(
        workflow,
        {
            ids[0]: build_meta("Text to Image", source_key="wf:text", image_number=1),
            ids[1]: build_meta("Text to Image", source_key="wf:text", image_number=2),
            ids[2]: build_meta("Text to Image", source_key="wf:text", image_number=3),
        },
    )

    assert projection.active_source_key == "wf:text"
    assert projection.active_set_index == 0
    assert projection.active_uuid is None


def test_projection_manual_single_item_grid_selection_stays_sticky() -> None:
    """Manual grid focus should preserve hierarchy for a one-image source."""

    workflow = WorkflowState()
    image_id = uuid4()
    workflow.output_image_uuids = [image_id]
    workflow.output_focus_mode = OutputFocusMode.MANUAL
    workflow.active_output_uuid = None
    workflow.active_output_set_index = 0
    workflow.active_output_source_key = "wf:upscale"

    projection = build_output_canvas_projection(
        workflow,
        {
            image_id: build_meta(
                "Diffusion Upscale",
                source_key="wf:upscale",
                image_number=1,
            )
        },
    )

    assert projection.active_source_key == "wf:upscale"
    assert projection.active_set_index == 0
    assert projection.active_uuid is None


def test_projection_stale_manual_concrete_selection_falls_back_to_source_set() -> None:
    """Stale manual UUID should use nearest item in the stored source and set."""

    workflow = WorkflowState()
    first_id = uuid4()
    second_id = uuid4()
    workflow.output_image_uuids = [first_id, second_id]
    workflow.output_focus_mode = OutputFocusMode.MANUAL
    workflow.active_output_uuid = uuid4()
    workflow.active_output_set_index = 2
    workflow.active_output_source_key = "wf:text"

    projection = build_output_canvas_projection(
        workflow,
        {
            first_id: build_meta("Text to Image", source_key="wf:text", image_number=1),
            second_id: build_meta(
                "Text to Image", source_key="wf:text", image_number=2
            ),
        },
    )

    assert projection.active_source_key == "wf:text"
    assert projection.active_set_index == 2
    assert projection.active_uuid == second_id


def test_projection_stale_manual_grid_source_falls_back_to_first_item() -> None:
    """Stale manual grid source should fall back deterministically."""

    workflow = WorkflowState()
    first_id = uuid4()
    second_id = uuid4()
    workflow.output_image_uuids = [first_id, second_id]
    workflow.output_focus_mode = OutputFocusMode.MANUAL
    workflow.active_output_uuid = None
    workflow.active_output_set_index = 0
    workflow.active_output_source_key = "missing"

    projection = build_output_canvas_projection(
        workflow,
        {
            first_id: build_meta("A", source_key="wf:a", image_number=1),
            second_id: build_meta("B", source_key="wf:b", image_number=1),
        },
    )

    assert projection.active_source_key == "wf:a"
    assert projection.active_set_index == 1
    assert projection.active_uuid == first_id

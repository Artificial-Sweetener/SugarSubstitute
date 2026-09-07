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

"""Verify Output projection batch placement and replacement semantics."""

from __future__ import annotations

from uuid import uuid4

from substitute.application.workflows import build_output_canvas_projection
from substitute.domain.workflow import OutputFocusMode, WorkflowState


from tests.application.workflows.output_canvas_projection.support import build_meta


def test_projection_fallback_placement_uses_unoccupied_restore_slots() -> None:
    """Missing-index restore/import records should fill deterministic free slots."""

    workflow = WorkflowState()
    explicit_id = uuid4()
    fallback_id = uuid4()
    workflow.output_image_uuids = [explicit_id, fallback_id]

    projection = build_output_canvas_projection(
        workflow,
        {
            explicit_id: build_meta("Text", source_key="wf:text", list_index=0),
            fallback_id: build_meta("Text", source_key="wf:text"),
        },
    )

    source = projection.sources[0]
    assert source.images_by_set[1].image_id == explicit_id
    assert source.images_by_set[2].image_id == fallback_id


def test_explicit_batch_coordinates_keep_every_image_without_overwrite() -> None:
    """Images sharing a Comfy list slot must remain separate batch results."""

    ids = (uuid4(), uuid4(), uuid4())
    workflow = WorkflowState(output_image_uuids=list(ids))
    metadata = {
        image_id: build_meta(
            "Direct",
            source_key="direct:source",
            list_index=0,
        )
        for image_id in ids
    }
    for batch_index, image_id in enumerate(ids):
        metadata[image_id].batch_index = batch_index

    projection = build_output_canvas_projection(workflow, metadata)

    source = projection.sources[0]
    assert tuple(source.images_by_set) == (1, 2, 3)
    assert tuple(item.image_id for item in source.images_by_set.values()) == ids
    assert tuple(
        item.position.batch_index if item.position is not None else None
        for item in source.images_by_set.values()
    ) == (0, 1, 2)


def test_sparse_later_batch_member_keeps_its_backend_slot() -> None:
    """A lone batch-index-one final should reserve slot one for its preview."""

    image_id = uuid4()
    workflow = WorkflowState(output_image_uuids=[image_id])
    metadata = {
        image_id: build_meta(
            "Text",
            source_key="wf:text",
            list_index=0,
            batch_index=1,
            generation_run_id="job-1",
            output_session_id="generate-click-1",
        )
    }

    projection = build_output_canvas_projection(workflow, metadata)

    source = projection.sources[0]
    assert tuple(source.images_by_set) == (2,)
    assert source.images_by_set[2].image_id == image_id
    assert projection.set_count == 2


def test_explicit_session_batches_ignore_callback_arrival_order() -> None:
    """Batch selectors should follow backend coordinates within one queued job."""

    batch_zero_id, batch_one_id, batch_two_id = uuid4(), uuid4(), uuid4()
    workflow = WorkflowState(
        output_image_uuids=[batch_one_id, batch_zero_id, batch_two_id]
    )
    metadata = {
        image_id: build_meta(
            "Text",
            source_key="wf:text",
            list_index=0,
            batch_index=batch_index,
            generation_run_id="job-1",
            output_session_id="generate-click-1",
        )
        for image_id, batch_index in (
            (batch_one_id, 1),
            (batch_zero_id, 0),
            (batch_two_id, 2),
        )
    }

    projection = build_output_canvas_projection(workflow, metadata)

    assert tuple(
        item.image_id for item in projection.sources[0].images_by_set.values()
    ) == (batch_zero_id, batch_one_id, batch_two_id)


def test_new_generation_replaces_an_occupied_batch_position() -> None:
    """A newer run should replace history at the same backend result position."""

    previous_id = uuid4()
    latest_id = uuid4()
    workflow = WorkflowState(
        output_image_uuids=[previous_id, latest_id],
        active_output_uuid=latest_id,
    )
    metadata = {
        previous_id: build_meta(
            "Direct",
            source_key="direct:source",
            list_index=0,
            generation_run_id="run-1",
            prompt_id="prompt-1",
            client_id="client-1",
            node_id="node-1",
        ),
        latest_id: build_meta(
            "Direct",
            source_key="direct:source",
            list_index=0,
            generation_run_id="run-2",
            prompt_id="prompt-2",
            client_id="client-2",
            node_id="node-1",
        ),
    }
    metadata[previous_id].batch_index = 0
    metadata[latest_id].batch_index = 0

    projection = build_output_canvas_projection(workflow, metadata)

    source = projection.sources[0]
    assert tuple(source.images_by_set) == (1,)
    assert source.images_by_set[1].image_id == latest_id
    assert projection.active_uuid == latest_id


def test_new_generation_preserves_manual_image_at_occupied_batch_position() -> None:
    """A newer result must not displace a concrete manual selection."""

    selected_id = uuid4()
    latest_id = uuid4()
    workflow = WorkflowState(
        output_image_uuids=[selected_id, latest_id],
        active_output_uuid=selected_id,
        active_output_source_key="direct:source",
        active_output_set_index=1,
        output_focus_mode=OutputFocusMode.MANUAL,
    )
    metadata = {
        selected_id: build_meta(
            "Direct",
            source_key="direct:source",
            list_index=0,
            generation_run_id="run-1",
            prompt_id="prompt-1",
            client_id="client-1",
            node_id="node-1",
        ),
        latest_id: build_meta(
            "Direct",
            source_key="direct:source",
            list_index=0,
            generation_run_id="run-2",
            prompt_id="prompt-2",
            client_id="client-2",
            node_id="node-1",
        ),
    }
    metadata[selected_id].batch_index = 0
    metadata[latest_id].batch_index = 0

    projection = build_output_canvas_projection(workflow, metadata)

    source = projection.sources[0]
    assert tuple(source.images_by_set) == (1,)
    assert source.images_by_set[1].image_id == selected_id
    assert projection.active_uuid == selected_id


def test_outer_batches_share_one_session_without_replacing_positions() -> None:
    """Backend positions from separate jobs in one Generate click should accumulate."""

    ids = tuple(uuid4() for _index in range(4))
    workflow = WorkflowState(output_image_uuids=list(ids))
    metadata = {
        image_id: build_meta(
            "Text",
            source_key="wf:text",
            image_number=index + 1,
            list_index=0,
            batch_index=index % 2,
            generation_run_id=f"job-{index // 2 + 1}",
            output_session_id="generate-click-1",
        )
        for index, image_id in enumerate(ids)
    }

    projection = build_output_canvas_projection(workflow, metadata)

    source = projection.sources[0]
    assert tuple(source.images_by_set) == (1, 2, 3, 4)
    assert tuple(item.image_id for item in source.images_by_set.values()) == ids


def test_projection_never_mixes_distinct_explicit_output_sessions() -> None:
    """Only the latest explicit generation session should be visible."""

    old_id = uuid4()
    new_id = uuid4()
    workflow = WorkflowState(output_image_uuids=[old_id, new_id])
    metadata = {
        old_id: build_meta(
            "Text",
            source_key="wf:text",
            list_index=0,
            batch_index=0,
            generation_run_id="job-old",
            output_session_id="generate-click-old",
        ),
        new_id: build_meta(
            "Text",
            source_key="wf:text",
            list_index=0,
            batch_index=0,
            generation_run_id="job-new",
            output_session_id="generate-click-new",
        ),
    }

    projection = build_output_canvas_projection(workflow, metadata)

    source = projection.sources[0]
    assert tuple(source.images_by_set) == (1,)
    assert source.images_by_set[1].image_id == new_id

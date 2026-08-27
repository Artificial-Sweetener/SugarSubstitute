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

"""Verify Output projection placement and backend identity contracts."""

from __future__ import annotations

from uuid import uuid4

from substitute.application.workflows import build_output_canvas_projection
from substitute.domain.workflow import WorkflowState


from tests.application.workflows.output_canvas_projection.support import build_meta


def test_projection_uses_backend_list_index_plus_one_for_live_slots() -> None:
    """Backend list indexes should define one-based canvas set placement."""

    workflow = WorkflowState()
    later_id = uuid4()
    first_id = uuid4()
    workflow.output_image_uuids = [later_id, first_id]

    projection = build_output_canvas_projection(
        workflow,
        {
            later_id: build_meta(
                "Text",
                source_key="wf:text",
                list_index=3,
                generation_run_id="run-1",
                prompt_id="prompt-1",
                client_id="client-1",
                node_id="node-1",
            ),
            first_id: build_meta(
                "Text",
                source_key="wf:text",
                list_index=0,
                generation_run_id="run-1",
                prompt_id="prompt-1",
                client_id="client-1",
                node_id="node-1",
            ),
        },
    )

    source = projection.sources[0]
    assert source.images_by_set[1].image_id == first_id
    assert source.images_by_set[4].image_id == later_id


def test_direct_sources_follow_numbered_manifest_order_not_event_arrival() -> None:
    """Concurrent recovery completion must not reorder direct source tabs."""

    second_id = uuid4()
    first_id = uuid4()
    workflow = WorkflowState(output_image_uuids=[second_id, first_id])
    metadata = {
        second_id: build_meta(
            "2",
            source_key="direct:blue:0",
            list_index=0,
        ),
        first_id: build_meta(
            "1",
            source_key="direct:red:0",
            list_index=0,
        ),
    }
    metadata[second_id].source_label = "2"
    metadata[second_id].batch_index = 0
    metadata[first_id].source_label = "1"
    metadata[first_id].batch_index = 0

    projection = build_output_canvas_projection(workflow, metadata)

    assert tuple(source.label for source in projection.sources) == ("1", "2")


def test_projection_rejects_backend_identity_without_list_index_fallback() -> None:
    """Backend-routed records without list placement should not use fallback slots."""

    workflow = WorkflowState()
    missing_id = uuid4()
    workflow.output_image_uuids = [missing_id]

    projection = build_output_canvas_projection(
        workflow,
        {
            missing_id: build_meta(
                "Text",
                source_key="wf:text",
                generation_run_id="run-1",
                prompt_id="prompt-1",
                client_id="client-1",
                node_id="node-1",
            ),
        },
    )

    assert projection.sources == ()
    assert projection.active_uuid is None


def test_projection_rejects_partial_backend_identity_without_list_index_fallback() -> (
    None
):
    """Partial backend identity should not be treated as restore/import output."""

    workflow = WorkflowState()
    missing_id = uuid4()
    workflow.output_image_uuids = [missing_id]

    projection = build_output_canvas_projection(
        workflow,
        {
            missing_id: build_meta(
                "Text",
                source_key="wf:text",
                generation_run_id="run-1",
                prompt_id="prompt-1",
                client_id="client-1",
            ),
        },
    )

    assert projection.sources == ()
    assert projection.active_uuid is None

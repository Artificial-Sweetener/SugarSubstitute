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

"""Verify Output projection source grouping and set derivation."""

from __future__ import annotations

from uuid import uuid4

from substitute.application.workflows import build_output_canvas_projection
from substitute.domain.workflow import WorkflowState


from tests.application.workflows.output_canvas_projection.support import build_meta


def test_projection_groups_one_source_single_image() -> None:
    """One output should create one source with a single set."""

    workflow = WorkflowState()
    image_id = uuid4()
    workflow.output_image_uuids = [image_id]
    workflow.active_output_uuid = image_id

    projection = build_output_canvas_projection(
        workflow,
        {image_id: build_meta("Text to Image", source_key="wf:1")},
    )

    assert projection.set_count == 1
    assert projection.active_source_key == "wf:1"
    assert projection.active_set_index == 1
    assert projection.active_uuid == image_id
    assert [source.label for source in projection.sources] == ["Text to Image"]
    assert projection.scene_count == 1
    assert projection.scene_groups[0].scene_key == ""
    assert projection.scene_groups[0].title == "Scene"
    assert projection.scene_groups[0].title_is_default is True
    assert projection.sources[0].label_is_default is False


def test_projection_marks_only_app_owned_source_fallback_as_default() -> None:
    """Authored text equal to a fallback must remain distinguishable and exact."""

    workflow = WorkflowState()
    fallback_id = uuid4()
    authored_id = uuid4()
    workflow.output_image_uuids = [fallback_id, authored_id]

    projection = build_output_canvas_projection(
        workflow,
        {
            fallback_id: build_meta("", source_key="fallback"),
            authored_id: build_meta("Output", source_key="authored"),
        },
    )

    assert projection.sources[0].label == "Output"
    assert projection.sources[0].label_is_default is True
    assert projection.sources[1].label == "Output"
    assert projection.sources[1].label_is_default is False


def test_projection_keeps_sources_separate_with_one_set_each() -> None:
    """Distinct output sources should become distinct source groups."""

    workflow = WorkflowState()
    text_id = uuid4()
    upscale_id = uuid4()
    workflow.output_image_uuids = [text_id, upscale_id]
    workflow.active_output_uuid = upscale_id

    projection = build_output_canvas_projection(
        workflow,
        {
            text_id: build_meta("Text to Image", source_key="wf:text"),
            upscale_id: build_meta("Diffusion Upscale", source_key="wf:upscale"),
        },
    )

    assert projection.set_count == 1
    assert [source.source_key for source in projection.sources] == [
        "wf:text",
        "wf:upscale",
    ]
    assert projection.active_source_key == "wf:upscale"


def test_projection_derives_set_indexes_per_source_order() -> None:
    """Batch images should become set indexes within each source group."""

    workflow = WorkflowState()
    ids = [uuid4() for _ in range(8)]
    workflow.output_image_uuids = ids
    workflow.active_output_uuid = ids[5]
    metadata = {
        ids[0]: build_meta("Text to Image", source_key="wf:text", image_number=1),
        ids[1]: build_meta(
            "Diffusion Upscale", source_key="wf:upscale", image_number=1
        ),
        ids[2]: build_meta("Text to Image", source_key="wf:text", image_number=2),
        ids[3]: build_meta(
            "Diffusion Upscale", source_key="wf:upscale", image_number=2
        ),
        ids[4]: build_meta("Text to Image", source_key="wf:text", image_number=3),
        ids[5]: build_meta(
            "Diffusion Upscale", source_key="wf:upscale", image_number=3
        ),
        ids[6]: build_meta("Text to Image", source_key="wf:text", image_number=4),
        ids[7]: build_meta(
            "Diffusion Upscale", source_key="wf:upscale", image_number=4
        ),
    }

    projection = build_output_canvas_projection(workflow, metadata)

    assert projection.set_count == 4
    assert projection.active_source_key == "wf:upscale"
    assert projection.active_set_index == 0
    assert projection.active_uuid is None
    text_group = projection.source_for_key("wf:text")
    assert text_group is not None
    assert text_group.images_by_set[4].image_id == ids[6]


def test_projection_keeps_duplicate_labels_separate_by_source_key() -> None:
    """Display label collisions should not merge distinct output sources."""

    workflow = WorkflowState()
    first_id = uuid4()
    second_id = uuid4()
    workflow.output_image_uuids = [first_id, second_id]

    projection = build_output_canvas_projection(
        workflow,
        {
            first_id: build_meta("Output", source_key="wf:a"),
            second_id: build_meta("Output", source_key="wf:b"),
        },
    )

    assert [source.source_key for source in projection.sources] == ["wf:a", "wf:b"]
    assert [source.label for source in projection.sources] == ["Output", "Output"]


def test_projection_merges_run_scoped_keys_for_the_same_output_node() -> None:
    """Restored finals and a new run must not duplicate the four cube tabs."""

    workflow = WorkflowState()
    ids = [uuid4() for _ in range(6)]
    workflow.output_image_uuids = ids
    metadata = {
        ids[0]: build_meta(
            "Text to Image",
            source_key="workflow-old:8",
            node_id="8",
            list_index=0,
        ),
        ids[1]: build_meta(
            "Diffusion Upscale",
            source_key="workflow-old:17",
            node_id="17",
            list_index=0,
        ),
        ids[2]: build_meta(
            "Text to Image",
            source_key="workflow-new:108",
            node_id="108",
            list_index=0,
        ),
        ids[3]: build_meta(
            "Diffusion Upscale",
            source_key="workflow-new:117",
            node_id="117",
            list_index=0,
        ),
        ids[4]: build_meta(
            "Automask Detailer",
            source_key="workflow-new:29",
            node_id="29",
            list_index=0,
        ),
        ids[5]: build_meta(
            "Automask Detailer 2",
            source_key="workflow-new:36",
            node_id="36",
            list_index=0,
        ),
    }

    projection = build_output_canvas_projection(workflow, metadata)

    assert [source.source_key for source in projection.sources] == [
        "cube:Text to Image",
        "cube:Diffusion Upscale",
        "cube:Automask Detailer",
        "cube:Automask Detailer 2",
    ]
    assert [source.label for source in projection.sources] == [
        "Text to Image",
        "Diffusion Upscale",
        "Automask Detailer",
        "Automask Detailer 2",
    ]


def test_projection_preserves_explicit_source_keys_unrelated_to_node_identity() -> None:
    """Authored source keys must remain distinct when node metadata is incidental."""

    workflow = WorkflowState()
    first_id = uuid4()
    second_id = uuid4()
    workflow.output_image_uuids = [first_id, second_id]

    projection = build_output_canvas_projection(
        workflow,
        {
            first_id: build_meta(
                "Output", source_key="alpha", node_id="7", list_index=0
            ),
            second_id: build_meta(
                "Output", source_key="beta", node_id="7", list_index=0
            ),
        },
    )

    assert [source.source_key for source in projection.sources] == ["alpha", "beta"]


def test_projection_allows_ragged_source_groups() -> None:
    """Sources with fewer set images should remain selectable."""

    workflow = WorkflowState()
    first_id = uuid4()
    second_id = uuid4()
    third_id = uuid4()
    workflow.output_image_uuids = [first_id, second_id, third_id]

    projection = build_output_canvas_projection(
        workflow,
        {
            first_id: build_meta("A", source_key="wf:a", image_number=1),
            second_id: build_meta("A", source_key="wf:a", image_number=2),
            third_id: build_meta("B", source_key="wf:b", image_number=1),
        },
    )

    assert projection.set_count == 2
    group_b = projection.source_for_key("wf:b")
    assert group_b is not None
    assert projection.item_for(source_key="wf:b", set_index=2) is None
    first_item = group_b.first_item()
    assert first_item is not None
    assert first_item.image_id == third_id

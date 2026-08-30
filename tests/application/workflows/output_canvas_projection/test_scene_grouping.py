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

"""Verify Output projection scene grouping and representatives."""

from __future__ import annotations

from uuid import UUID, uuid4

from substitute.application.workflows import build_output_canvas_projection
from substitute.domain.workflow import ImageMeta, WorkflowState


from tests.application.workflows.output_canvas_projection.support import build_meta


def test_direct_scene_groups_preserve_source_order_and_every_batch_item() -> None:
    """Each scene should independently retain numbered sources and tensor batches."""

    metadata: dict[UUID, ImageMeta] = {}
    image_ids: list[UUID] = []
    for scene_order, scene_key in enumerate(("day", "night")):
        for source_label, source_key in (("2", "direct:blue:0"), ("1", "direct:red:0")):
            for batch_index in (1, 0):
                image_id = uuid4()
                image_ids.append(image_id)
                image_meta = build_meta(
                    source_label,
                    source_key=source_key,
                    scene_key=scene_key,
                    scene_title=scene_key.title(),
                    scene_order=scene_order,
                    scene_count=2,
                    list_index=0,
                )
                image_meta.batch_index = batch_index
                metadata[image_id] = image_meta
    workflow = WorkflowState(output_image_uuids=image_ids)

    projection = build_output_canvas_projection(workflow, metadata)

    assert tuple(scene.scene_key for scene in projection.scene_groups) == (
        "day",
        "night",
    )
    for scene in projection.scene_groups:
        assert tuple(source.label for source in scene.sources) == ("1", "2")
        assert all(tuple(source.images_by_set) == (1, 2) for source in scene.sources)
        assert all(
            tuple(
                item.position.batch_index
                for item in source.images_by_set.values()
                if item.position is not None
            )
            == (0, 1)
            for source in scene.sources
        )


def test_projection_keeps_duplicate_labels_separate_inside_scene_groups() -> None:
    """Scene source grouping should use source keys even when labels collide."""

    workflow = WorkflowState()
    first_id = uuid4()
    second_id = uuid4()
    workflow.output_image_uuids = [first_id, second_id]

    projection = build_output_canvas_projection(
        workflow,
        {
            first_id: build_meta(
                "Output",
                source_key="wf:a",
                scene_key="scene-a",
                scene_title="Scene",
                scene_order=0,
            ),
            second_id: build_meta(
                "Output",
                source_key="wf:b",
                scene_key="scene-a",
                scene_title="Scene",
                scene_order=0,
            ),
        },
    )

    scene = projection.scene_groups[0]
    assert [source.source_key for source in scene.sources] == ["wf:a", "wf:b"]
    assert [source.label for source in scene.sources] == ["Output", "Output"]


def test_projection_groups_outputs_by_scene_above_sources() -> None:
    """Scene metadata should build scene groups while preserving source batches."""

    workflow = WorkflowState()
    ids = [uuid4(), uuid4(), uuid4(), uuid4()]
    workflow.output_image_uuids = ids
    workflow.active_output_uuid = ids[2]
    metadata = {
        ids[0]: build_meta(
            "Text",
            source_key="wf:text",
            image_number=1,
            scene_key="portrait",
            scene_title="Portrait",
            scene_order=0,
        ),
        ids[1]: build_meta(
            "Upscale",
            source_key="wf:upscale",
            image_number=1,
            scene_key="portrait",
            scene_title="Portrait",
            scene_order=0,
        ),
        ids[2]: build_meta(
            "Text",
            source_key="wf:text",
            image_number=1,
            scene_key="cafe",
            scene_title="Cafe",
            scene_order=1,
        ),
        ids[3]: build_meta(
            "Text",
            source_key="wf:text",
            image_number=2,
            scene_key="cafe",
            scene_title="Cafe",
            scene_order=1,
        ),
    }

    projection = build_output_canvas_projection(workflow, metadata)

    assert projection.scene_count == 2
    assert [scene.scene_key for scene in projection.scene_groups] == [
        "portrait",
        "cafe",
    ]
    assert [scene.title for scene in projection.scene_groups] == ["Portrait", "Cafe"]
    assert [source.source_key for source in projection.scene_groups[0].sources] == [
        "wf:text",
        "wf:upscale",
    ]
    cafe_text = projection.scene_groups[1].sources[0]
    assert cafe_text.images_by_set[2].image_id == ids[3]
    assert projection.active_scene_key == "cafe"


def test_projection_keeps_duplicate_scene_titles_separate_by_scene_key() -> None:
    """Scene grouping should use scene key, not display title."""

    workflow = WorkflowState()
    first_id = uuid4()
    second_id = uuid4()
    workflow.output_image_uuids = [first_id, second_id]

    projection = build_output_canvas_projection(
        workflow,
        {
            first_id: build_meta(
                "Text",
                source_key="wf:text",
                scene_key="scene-b",
                scene_title="Duplicate",
                scene_order=1,
            ),
            second_id: build_meta(
                "Text",
                source_key="wf:text",
                scene_key="scene-a",
                scene_title="Duplicate",
                scene_order=0,
            ),
        },
    )

    assert [scene.scene_key for scene in projection.scene_groups] == [
        "scene-a",
        "scene-b",
    ]
    assert [scene.title for scene in projection.scene_groups] == [
        "Duplicate",
        "Duplicate",
    ]


def test_projection_scene_representative_uses_terminal_source_first_batch() -> None:
    """Scene overview representative should use the terminal source slot."""

    workflow = WorkflowState()
    ids = [uuid4() for _ in range(6)]
    workflow.output_image_uuids = ids
    metadata = {
        ids[0]: build_meta(
            "Text",
            source_key="wf:text",
            image_number=1,
            scene_key="cafe",
            scene_title="Cafe",
            scene_order=0,
        ),
        ids[1]: build_meta(
            "Text",
            source_key="wf:text",
            image_number=2,
            scene_key="cafe",
            scene_title="Cafe",
            scene_order=0,
        ),
        ids[2]: build_meta(
            "Upscale",
            source_key="wf:upscale",
            image_number=1,
            scene_key="cafe",
            scene_title="Cafe",
            scene_order=0,
        ),
        ids[3]: build_meta(
            "Upscale",
            source_key="wf:upscale",
            image_number=2,
            scene_key="cafe",
            scene_title="Cafe",
            scene_order=0,
        ),
        ids[4]: build_meta(
            "Upscale",
            source_key="wf:upscale",
            image_number=3,
            scene_key="cafe",
            scene_title="Cafe",
            scene_order=0,
        ),
        ids[5]: build_meta(
            "Text",
            source_key="wf:text",
            image_number=3,
            scene_key="cafe",
            scene_title="Cafe",
            scene_order=0,
        ),
    }

    projection = build_output_canvas_projection(workflow, metadata)

    scene = projection.scene_groups[0]
    assert scene.primary_image_id == ids[2]
    assert scene.representative_source_key == "wf:upscale"
    assert scene.representative_set_index == 1

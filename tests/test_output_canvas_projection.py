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

"""Contract tests for grouped output canvas projection behavior."""

from __future__ import annotations

from uuid import uuid4

from substitute.application.workflows import build_output_canvas_projection
from substitute.domain.workflow import ImageMeta, OutputFocusMode, WorkflowState


def _meta(
    label: str,
    *,
    source_key: str,
    image_number: int = 1,
    scene_key: str = "",
    scene_title: str = "",
    scene_order: int | None = None,
    scene_count: int | None = None,
    list_index: int | None = None,
    generation_run_id: str = "",
    prompt_id: str = "",
    client_id: str = "",
    node_id: str = "",
) -> ImageMeta:
    """Build output metadata for projection tests."""

    return ImageMeta(
        workflow_name="Recipe",
        cube_name=label,
        image_number=image_number,
        suffix="",
        path=f"E:/outputs/{source_key}_{image_number}.png",
        source_key=source_key,
        source_label=label,
        scene_key=scene_key,
        scene_title=scene_title,
        scene_order=scene_order,
        scene_count=scene_count,
        list_index=list_index,
        generation_run_id=generation_run_id,
        prompt_id=prompt_id,
        client_id=client_id,
        node_id=node_id,
    )


def test_projection_groups_one_source_single_image() -> None:
    """One output should create one source with a single set."""

    workflow = WorkflowState()
    image_id = uuid4()
    workflow.output_image_uuids = [image_id]
    workflow.active_output_uuid = image_id

    projection = build_output_canvas_projection(
        workflow,
        {image_id: _meta("Text to Image", source_key="wf:1")},
    )

    assert projection.set_count == 1
    assert projection.active_source_key == "wf:1"
    assert projection.active_set_index == 1
    assert projection.active_uuid == image_id
    assert [source.label for source in projection.sources] == ["Text to Image"]
    assert projection.scene_count == 1
    assert projection.scene_groups[0].scene_key == ""
    assert projection.scene_groups[0].title == "Scene"


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
            text_id: _meta("Text to Image", source_key="wf:text"),
            upscale_id: _meta("Diffusion Upscale", source_key="wf:upscale"),
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
        ids[0]: _meta("Text to Image", source_key="wf:text", image_number=1),
        ids[1]: _meta("Diffusion Upscale", source_key="wf:upscale", image_number=1),
        ids[2]: _meta("Text to Image", source_key="wf:text", image_number=2),
        ids[3]: _meta("Diffusion Upscale", source_key="wf:upscale", image_number=2),
        ids[4]: _meta("Text to Image", source_key="wf:text", image_number=3),
        ids[5]: _meta("Diffusion Upscale", source_key="wf:upscale", image_number=3),
        ids[6]: _meta("Text to Image", source_key="wf:text", image_number=4),
        ids[7]: _meta("Diffusion Upscale", source_key="wf:upscale", image_number=4),
    }

    projection = build_output_canvas_projection(workflow, metadata)

    assert projection.set_count == 4
    assert projection.active_source_key == "wf:upscale"
    assert projection.active_set_index == 0
    assert projection.active_uuid is None
    text_group = projection.source_for_key("wf:text")
    assert text_group is not None
    assert text_group.images_by_set[4].image_id == ids[6]


def test_projection_uses_backend_list_index_plus_one_for_live_slots() -> None:
    """Backend list indexes should define one-based canvas set placement."""

    workflow = WorkflowState()
    later_id = uuid4()
    first_id = uuid4()
    workflow.output_image_uuids = [later_id, first_id]

    projection = build_output_canvas_projection(
        workflow,
        {
            later_id: _meta(
                "Text",
                source_key="wf:text",
                list_index=3,
                generation_run_id="run-1",
                prompt_id="prompt-1",
                client_id="client-1",
                node_id="node-1",
            ),
            first_id: _meta(
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


def test_projection_fallback_placement_uses_unoccupied_restore_slots() -> None:
    """Missing-index restore/import records should fill deterministic free slots."""

    workflow = WorkflowState()
    explicit_id = uuid4()
    fallback_id = uuid4()
    workflow.output_image_uuids = [explicit_id, fallback_id]

    projection = build_output_canvas_projection(
        workflow,
        {
            explicit_id: _meta("Text", source_key="wf:text", list_index=0),
            fallback_id: _meta("Text", source_key="wf:text"),
        },
    )

    source = projection.sources[0]
    assert source.images_by_set[1].image_id == explicit_id
    assert source.images_by_set[2].image_id == fallback_id


def test_projection_rejects_backend_identity_without_list_index_fallback() -> None:
    """Backend-routed records without list placement should not use fallback slots."""

    workflow = WorkflowState()
    missing_id = uuid4()
    workflow.output_image_uuids = [missing_id]

    projection = build_output_canvas_projection(
        workflow,
        {
            missing_id: _meta(
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
            missing_id: _meta(
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


def test_projection_falls_back_when_active_uuid_is_stale() -> None:
    """A stale active UUID should select the first available source item."""

    workflow = WorkflowState()
    first_id = uuid4()
    workflow.output_image_uuids = [first_id]
    workflow.active_output_uuid = uuid4()

    projection = build_output_canvas_projection(
        workflow,
        {first_id: _meta("Text to Image", source_key="wf:text")},
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
            ids[0]: _meta("Text to Image", source_key="wf:text", image_number=1),
            ids[1]: _meta("Text to Image", source_key="wf:text", image_number=2),
            ids[2]: _meta("Text to Image", source_key="wf:text", image_number=3),
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
            ids[0]: _meta("Text to Image", source_key="wf:text", image_number=1),
            ids[1]: _meta("Text to Image", source_key="wf:text", image_number=2),
            ids[2]: _meta("Text to Image", source_key="wf:text", image_number=3),
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
            ids[0]: _meta("Text to Image", source_key="wf:text", image_number=1),
            ids[1]: _meta("Text to Image", source_key="wf:text", image_number=2),
            ids[2]: _meta("Text to Image", source_key="wf:text", image_number=3),
        },
    )

    assert projection.active_source_key == "wf:text"
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
            first_id: _meta("Text to Image", source_key="wf:text", image_number=1),
            second_id: _meta("Text to Image", source_key="wf:text", image_number=2),
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
            first_id: _meta("A", source_key="wf:a", image_number=1),
            second_id: _meta("B", source_key="wf:b", image_number=1),
        },
    )

    assert projection.active_source_key == "wf:a"
    assert projection.active_set_index == 1
    assert projection.active_uuid == first_id


def test_projection_keeps_duplicate_labels_separate_by_source_key() -> None:
    """Display label collisions should not merge distinct output sources."""

    workflow = WorkflowState()
    first_id = uuid4()
    second_id = uuid4()
    workflow.output_image_uuids = [first_id, second_id]

    projection = build_output_canvas_projection(
        workflow,
        {
            first_id: _meta("Output", source_key="wf:a"),
            second_id: _meta("Output", source_key="wf:b"),
        },
    )

    assert [source.source_key for source in projection.sources] == ["wf:a", "wf:b"]
    assert [source.label for source in projection.sources] == ["Output", "Output"]


def test_projection_keeps_duplicate_labels_separate_inside_scene_groups() -> None:
    """Scene source grouping should use source keys even when labels collide."""

    workflow = WorkflowState()
    first_id = uuid4()
    second_id = uuid4()
    workflow.output_image_uuids = [first_id, second_id]

    projection = build_output_canvas_projection(
        workflow,
        {
            first_id: _meta(
                "Output",
                source_key="wf:a",
                scene_key="scene-a",
                scene_title="Scene",
                scene_order=0,
            ),
            second_id: _meta(
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
            first_id: _meta("A", source_key="wf:a", image_number=1),
            second_id: _meta("A", source_key="wf:a", image_number=2),
            third_id: _meta("B", source_key="wf:b", image_number=1),
        },
    )

    assert projection.set_count == 2
    group_b = projection.source_for_key("wf:b")
    assert group_b is not None
    nearest_item = group_b.nearest_item(2)
    assert nearest_item is not None
    assert nearest_item.image_id == third_id


def test_projection_groups_outputs_by_scene_above_sources() -> None:
    """Scene metadata should build scene groups while preserving source batches."""

    workflow = WorkflowState()
    ids = [uuid4(), uuid4(), uuid4(), uuid4()]
    workflow.output_image_uuids = ids
    workflow.active_output_uuid = ids[2]
    metadata = {
        ids[0]: _meta(
            "Text",
            source_key="wf:text",
            image_number=1,
            scene_key="portrait",
            scene_title="Portrait",
            scene_order=0,
        ),
        ids[1]: _meta(
            "Upscale",
            source_key="wf:upscale",
            image_number=1,
            scene_key="portrait",
            scene_title="Portrait",
            scene_order=0,
        ),
        ids[2]: _meta(
            "Text",
            source_key="wf:text",
            image_number=1,
            scene_key="cafe",
            scene_title="Cafe",
            scene_order=1,
        ),
        ids[3]: _meta(
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
            first_id: _meta(
                "Text",
                source_key="wf:text",
                scene_key="scene-b",
                scene_title="Duplicate",
                scene_order=1,
            ),
            second_id: _meta(
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
        ids[0]: _meta(
            "Text",
            source_key="wf:text",
            image_number=1,
            scene_key="cafe",
            scene_title="Cafe",
            scene_order=0,
        ),
        ids[1]: _meta(
            "Text",
            source_key="wf:text",
            image_number=2,
            scene_key="cafe",
            scene_title="Cafe",
            scene_order=0,
        ),
        ids[2]: _meta(
            "Upscale",
            source_key="wf:upscale",
            image_number=1,
            scene_key="cafe",
            scene_title="Cafe",
            scene_order=0,
        ),
        ids[3]: _meta(
            "Upscale",
            source_key="wf:upscale",
            image_number=2,
            scene_key="cafe",
            scene_title="Cafe",
            scene_order=0,
        ),
        ids[4]: _meta(
            "Upscale",
            source_key="wf:upscale",
            image_number=3,
            scene_key="cafe",
            scene_title="Cafe",
            scene_order=0,
        ),
        ids[5]: _meta(
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


def test_projection_automatic_multi_scene_same_source_stays_on_scene_overview() -> None:
    """Automatic scene runs should not promote cross-scene source groups to grids."""

    workflow = WorkflowState()
    ids = [uuid4(), uuid4()]
    workflow.output_image_uuids = ids
    workflow.active_output_uuid = ids[-1]
    workflow.active_output_source_key = "wf:text"
    metadata = {
        ids[0]: _meta(
            "Text",
            source_key="wf:text",
            image_number=1,
            scene_key="portrait",
            scene_title="Portrait",
            scene_order=0,
            scene_count=2,
        ),
        ids[1]: _meta(
            "Text",
            source_key="wf:text",
            image_number=1,
            scene_key="cafe",
            scene_title="Cafe",
            scene_order=1,
            scene_count=2,
        ),
    }

    projection = build_output_canvas_projection(workflow, metadata)

    assert projection.scene_count == 2
    assert projection.active_scene_overview is True
    assert projection.active_scene_key == "cafe"
    assert projection.active_set_index == 1
    assert projection.active_uuid is None


def test_projection_manual_scene_overview_stays_on_scene_overview() -> None:
    """Manual All selection should remain active across later scene outputs."""

    workflow = WorkflowState()
    ids = [uuid4(), uuid4()]
    workflow.output_image_uuids = ids
    workflow.output_focus_mode = OutputFocusMode.MANUAL
    workflow.active_output_scene_overview = True
    workflow.active_output_scene_key = "portrait"
    workflow.active_output_uuid = None
    workflow.active_output_source_key = None
    workflow.active_output_set_index = 1
    metadata = {
        ids[0]: _meta(
            "Text",
            source_key="wf:text",
            image_number=1,
            scene_key="portrait",
            scene_title="Portrait",
            scene_order=0,
            scene_count=2,
        ),
        ids[1]: _meta(
            "Text",
            source_key="wf:text",
            image_number=1,
            scene_key="cafe",
            scene_title="Cafe",
            scene_order=1,
            scene_count=2,
        ),
    }

    projection = build_output_canvas_projection(workflow, metadata)

    assert projection.active_scene_overview is True
    assert projection.active_scene_key == "portrait"
    assert projection.active_source_key is None
    assert projection.active_set_index == 1
    assert projection.active_uuid is None


def test_projection_manual_concrete_scene_scopes_focus_to_scene_sources() -> None:
    """Manual scene grid focus should resolve inside the selected scene only."""

    workflow = WorkflowState()
    ids = [uuid4() for _ in range(4)]
    workflow.output_image_uuids = ids
    workflow.output_focus_mode = OutputFocusMode.MANUAL
    workflow.active_output_scene_key = "portrait"
    workflow.active_output_scene_overview = False
    workflow.active_output_uuid = None
    workflow.active_output_source_key = "wf:text"
    workflow.active_output_set_index = 0
    metadata = {
        ids[0]: _meta(
            "Text",
            source_key="wf:text",
            image_number=1,
            scene_key="portrait",
            scene_title="Portrait",
            scene_order=0,
            scene_count=2,
        ),
        ids[1]: _meta(
            "Text",
            source_key="wf:text",
            image_number=2,
            scene_key="portrait",
            scene_title="Portrait",
            scene_order=0,
            scene_count=2,
        ),
        ids[2]: _meta(
            "Text",
            source_key="wf:text",
            image_number=1,
            scene_key="cafe",
            scene_title="Cafe",
            scene_order=1,
            scene_count=2,
        ),
        ids[3]: _meta(
            "Text",
            source_key="wf:text",
            image_number=2,
            scene_key="cafe",
            scene_title="Cafe",
            scene_order=1,
            scene_count=2,
        ),
    }

    projection = build_output_canvas_projection(workflow, metadata)

    assert projection.active_scene_overview is False
    assert projection.active_scene_key == "portrait"
    assert projection.active_source_key == "wf:text"
    assert projection.active_set_index == 0
    assert projection.active_uuid is None


def test_projection_uses_declared_scene_count_before_all_scenes_finish() -> None:
    """Scene navigation should know a multi-scene run before every scene has output."""

    workflow = WorkflowState()
    image_id = uuid4()
    workflow.output_image_uuids = [image_id]
    workflow.active_output_uuid = image_id

    projection = build_output_canvas_projection(
        workflow,
        {
            image_id: _meta(
                "Text",
                source_key="wf:text",
                scene_key="portrait",
                scene_title="Portrait",
                scene_order=0,
                scene_count=3,
            )
        },
    )

    assert projection.scene_count == 3
    assert projection.active_scene_overview is True
    assert projection.active_scene_key == "portrait"

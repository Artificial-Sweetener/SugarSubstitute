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

"""Verify preview retirement plans and cache mutation."""

from __future__ import annotations

from uuid import uuid4

from substitute.application.workflows.output_preview_lifecycle_service import (
    PreviewSlotKey,
    ScenePreviewSlot,
    SourcePreviewSlotKey,
    apply_preview_retirement_plan,
    preview_retirement_plan,
    scene_group_without_preview,
)


from tests.application.workflows.output_preview_lifecycle.support import (
    build_scene,
    build_source,
)


def test_scene_group_without_preview_preserves_final_scene_metadata() -> None:
    """Retired scene previews should preserve final output and representative metadata."""

    final_id = uuid4()
    preview_id = uuid4()
    scene = build_scene(
        sources=(build_source("wf:text", "Text", {1: final_id}),),
        primary_image_id=final_id,
        preview_image_id=preview_id,
        representative_source_key="wf:text",
        representative_set_index=1,
        status="running",
    )

    cleared_scene = scene_group_without_preview(scene)

    assert cleared_scene.preview_image_id is None
    assert cleared_scene.primary_image_id == final_id
    assert cleared_scene.representative_source_key == "wf:text"
    assert cleared_scene.representative_set_index == 1
    assert cleared_scene.status == "running"
    assert cleared_scene.sources == scene.sources


def test_preview_retirement_plan_reports_registry_and_scene_mutations() -> None:
    """Preview retirement should identify all cache keys and scene DTO updates."""

    preview_id = uuid4()
    final_id = uuid4()
    source_slot = SourcePreviewSlotKey(
        scene_run_id="scene-run",
        generation_run_id="generation-run",
        scene_key="portrait",
        source_key="wf:text",
        set_index=1,
    )
    scene_slot = PreviewSlotKey(
        scene_run_id="scene-run",
        generation_run_id="generation-run",
        scene_key="portrait",
        source_key="wf:upscale",
        set_index=1,
    )
    source = build_source("wf:text", "Text", {1: final_id})

    plan = preview_retirement_plan(
        preview_id=preview_id,
        source_preview_ids_by_key={"wf:text": preview_id, "wf:other": uuid4()},
        source_preview_ids_by_slot={source_slot: preview_id},
        scene_preview_ids_by_slot={scene_slot: preview_id},
        scene_preview_slots_by_key={
            "portrait": ScenePreviewSlot(
                scene_run_id="scene-run",
                generation_run_id="generation-run",
                scene_key="portrait",
                source_key="wf:upscale",
                set_index=1,
                preview_id=preview_id,
            )
        },
        preview_scene_groups_by_key={
            "portrait": build_scene(
                sources=(source,),
                primary_image_id=final_id,
                preview_image_id=preview_id,
                representative_source_key="wf:text",
                representative_set_index=1,
            ),
            "draft": build_scene(
                sources=(),
                scene_key="draft",
                preview_image_id=preview_id,
            ),
        },
        base_scene_groups_by_key={
            "fallback": build_scene(
                sources=(source,),
                scene_key="fallback",
                primary_image_id=final_id,
                preview_image_id=preview_id,
            )
        },
    )

    assert plan.removed_source_keys == ("wf:text",)
    assert plan.removed_source_slots == (source_slot,)
    assert plan.removed_scene_slots == (scene_slot,)
    assert plan.removed_accepted_scene_keys == ("portrait",)
    assert plan.removed_preview_scene_group_keys == ("draft",)
    updated_groups = dict(plan.updated_preview_scene_groups)
    assert set(updated_groups) == {"portrait", "fallback"}
    assert updated_groups["portrait"].preview_image_id is None
    assert updated_groups["portrait"].primary_image_id == final_id
    assert updated_groups["fallback"].preview_image_id is None
    assert updated_groups["fallback"].primary_image_id == final_id


def test_apply_preview_retirement_plan_updates_preview_maps() -> None:
    """Preview retirement application should stay in the lifecycle service."""

    preview_id = uuid4()
    retained_preview_id = uuid4()
    final_id = uuid4()
    source_slot = SourcePreviewSlotKey(
        scene_run_id="scene-run",
        generation_run_id="generation-run",
        scene_key="portrait",
        source_key="wf:text",
        set_index=1,
    )
    scene_slot = PreviewSlotKey(
        scene_run_id="scene-run",
        generation_run_id="generation-run",
        scene_key="portrait",
        source_key="wf:upscale",
        set_index=1,
    )
    updated_scene = build_scene(
        sources=(),
        primary_image_id=final_id,
        preview_image_id=None,
        representative_source_key="wf:text",
    )
    retirement = preview_retirement_plan(
        preview_id=preview_id,
        source_preview_ids_by_key={
            "wf:text": preview_id,
            "wf:other": retained_preview_id,
        },
        source_preview_ids_by_slot={source_slot: preview_id},
        scene_preview_ids_by_slot={scene_slot: preview_id},
        scene_preview_slots_by_key={
            "portrait": ScenePreviewSlot(
                scene_run_id="scene-run",
                generation_run_id="generation-run",
                scene_key="portrait",
                source_key="wf:upscale",
                set_index=1,
                preview_id=preview_id,
            )
        },
        preview_scene_groups_by_key={
            "portrait": build_scene(
                sources=(),
                primary_image_id=final_id,
                preview_image_id=preview_id,
                representative_source_key="wf:text",
            ),
            "draft": build_scene(
                sources=(), scene_key="draft", preview_image_id=preview_id
            ),
        },
        base_scene_groups_by_key={"portrait": updated_scene},
    )
    source_preview_ids_by_key = {
        "wf:text": preview_id,
        "wf:other": retained_preview_id,
    }
    preview_labels_by_source_key = {"wf:text": "Text", "wf:other": "Other"}
    preview_images_by_source_key: dict[str, object] = {
        "wf:text": object(),
        "wf:other": object(),
    }
    source_preview_ids_by_slot = {source_slot: preview_id}
    scene_preview_ids_by_slot = {scene_slot: preview_id}
    scene_preview_slots_by_key = {
        "portrait": ScenePreviewSlot(
            scene_run_id="scene-run",
            generation_run_id="generation-run",
            scene_key="portrait",
            source_key="wf:upscale",
            set_index=1,
            preview_id=preview_id,
        )
    }
    preview_scene_groups_by_key = {
        "portrait": build_scene(
            sources=(),
            primary_image_id=final_id,
            preview_image_id=preview_id,
            representative_source_key="wf:text",
        ),
        "draft": build_scene(
            sources=(), scene_key="draft", preview_image_id=preview_id
        ),
    }

    apply_preview_retirement_plan(
        retirement,
        source_preview_ids_by_key=source_preview_ids_by_key,
        preview_labels_by_source_key=preview_labels_by_source_key,
        preview_images_by_source_key=preview_images_by_source_key,
        source_preview_ids_by_slot=source_preview_ids_by_slot,
        scene_preview_ids_by_slot=scene_preview_ids_by_slot,
        scene_preview_slots_by_key=scene_preview_slots_by_key,
        preview_scene_groups_by_key=preview_scene_groups_by_key,
    )

    assert source_preview_ids_by_key == {"wf:other": retained_preview_id}
    assert preview_labels_by_source_key == {"wf:other": "Other"}
    assert set(preview_images_by_source_key) == {"wf:other"}
    assert source_preview_ids_by_slot == {}
    assert scene_preview_ids_by_slot == {}
    assert scene_preview_slots_by_key == {}
    assert set(preview_scene_groups_by_key) == {"portrait"}
    assert preview_scene_groups_by_key["portrait"].preview_image_id is None
    assert preview_scene_groups_by_key["portrait"].primary_image_id == final_id

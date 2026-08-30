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

"""Verify representative scene preview selection and completion policy."""

from __future__ import annotations

from uuid import uuid4

from substitute.application.workflows.output_preview_lifecycle_service import (
    PreviewSlotKey,
    ScenePreviewSlot,
    preview_slot_for_scene,
    preview_slot_is_completed,
    scene_preview_matches_representative,
    source_is_after,
    source_is_new_for_scene,
)


from tests.application.workflows.output_preview_lifecycle.support import (
    build_scene,
    build_source,
)


def test_representative_preview_prefers_later_or_new_sources() -> None:
    """Scene overview previews should advance to later or newly introduced sources."""

    scene = build_scene(
        sources=(
            build_source("wf:text", "Text", {1: uuid4()}),
            build_source("wf:upscale", "Upscale", {1: uuid4()}),
        ),
        representative_source_key="wf:text",
    )
    current_slot = ScenePreviewSlot(
        scene_run_id="scene-run",
        scene_key="portrait",
        source_key="wf:text",
        set_index=1,
        preview_id=uuid4(),
    )

    assert scene_preview_matches_representative(
        scene=scene,
        current_slot=current_slot,
        source_key="wf:upscale",
    )
    assert scene_preview_matches_representative(
        scene=scene,
        current_slot=current_slot,
        source_key="wf:new-node",
    )
    assert source_is_after(scene, "wf:upscale", "wf:text")
    assert source_is_new_for_scene(scene, "wf:new-node")


def test_representative_preview_rejects_earlier_completed_source_slot() -> None:
    """Scene overview previews should reject sources before the representative final."""

    scene = build_scene(
        sources=(
            build_source("wf:text", "Text", {1: uuid4()}),
            build_source("wf:upscale", "Upscale", {}),
        ),
        representative_source_key="wf:upscale",
    )

    assert not scene_preview_matches_representative(
        scene=scene,
        current_slot=None,
        source_key="wf:text",
    )
    assert scene_preview_matches_representative(
        scene=scene,
        current_slot=None,
        source_key="wf:upscale",
    )


def test_preview_slot_is_completed_uses_completed_slots_and_scene_outputs() -> None:
    """Preview slots should complete from explicit slots or matching scene outputs."""

    completed_slot = PreviewSlotKey(
        scene_run_id="scene-run",
        generation_run_id="generation-run",
        scene_key="portrait",
        source_key="wf:text",
        set_index=1,
    )
    scene = build_scene(
        scene_run_id="scene-run",
        sources=(build_source("wf:upscale", "Upscale", {2: uuid4()}),),
    )

    assert preview_slot_is_completed(
        slot_key=completed_slot,
        scene=scene,
        completed_preview_slots={completed_slot},
    )
    assert preview_slot_is_completed(
        slot_key=PreviewSlotKey("scene-run", "portrait", "wf:upscale", 2),
        scene=scene,
        completed_preview_slots=set(),
    )
    assert not preview_slot_is_completed(
        slot_key=PreviewSlotKey("other-run", "portrait", "wf:upscale", 2),
        scene=scene,
        completed_preview_slots=set(),
    )

    prior_generation_scene = build_scene(
        scene_run_id="scene-run",
        sources=(
            build_source(
                "wf:upscale",
                "Upscale",
                {2: uuid4()},
                generation_run_id="prior-generation",
            ),
        ),
    )
    assert not preview_slot_is_completed(
        slot_key=completed_slot,
        scene=prior_generation_scene,
        completed_preview_slots=set(),
    )


def test_preview_slot_for_scene_returns_only_valid_representative_slots() -> None:
    """Scene preview slots should be accepted only while cached and representative."""

    preview_id = uuid4()
    scene = build_scene(
        sources=(
            build_source("wf:text", "Text", {1: uuid4()}),
            build_source("wf:upscale", "Upscale", {}),
        ),
        primary_image_id=uuid4(),
        representative_source_key="wf:text",
    )
    preview_slot = ScenePreviewSlot(
        scene_run_id="scene-run",
        scene_key="portrait",
        source_key="wf:upscale",
        set_index=1,
        preview_id=preview_id,
    )

    assert (
        preview_slot_for_scene(
            scene=scene,
            preview_slot=preview_slot,
            cached_preview_ids={preview_id},
            completed_preview_slots=set(),
        )
        == preview_slot
    )
    assert (
        preview_slot_for_scene(
            scene=scene,
            preview_slot=preview_slot,
            cached_preview_ids=set(),
            completed_preview_slots=set(),
        )
        is None
    )
    assert (
        preview_slot_for_scene(
            scene=scene,
            preview_slot=preview_slot,
            cached_preview_ids={preview_id},
            completed_preview_slots={preview_slot.preview_key()},
        )
        is None
    )

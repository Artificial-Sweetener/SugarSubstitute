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

"""Verify Output preview slot identity and completed-output matching."""

from __future__ import annotations

from uuid import UUID, uuid4

from substitute.application.workflows.output_preview_lifecycle_service import (
    PreviewSlotKey,
    ScenePreviewSlot,
    preview_slot_matches_completed_output,
    scene_has_completed_source_label_set,
    scene_has_completed_source_set,
    scene_preview_id_for_source,
    source_label_for_key,
    source_labels_match,
)


from tests.application.workflows.output_preview_lifecycle.support import (
    build_scene,
    build_source,
)


def test_scene_preview_slot_returns_completed_slot_key() -> None:
    """Scene preview slots should expose the final-output key they represent."""

    preview_id = uuid4()
    slot = ScenePreviewSlot(
        scene_run_id="scene-run",
        generation_run_id="generation-run",
        scene_key="portrait",
        source_key="wf:upscale",
        set_index=2,
        preview_id=preview_id,
        source_label="Upscale",
    )

    assert slot.source_set() == ("wf:upscale", 2)
    assert slot.preview_key() == PreviewSlotKey(
        scene_run_id="scene-run",
        generation_run_id="generation-run",
        scene_key="portrait",
        source_key="wf:upscale",
        set_index=2,
    )


def test_completed_source_detection_uses_source_key_and_label() -> None:
    """Completed output checks should match source identity or display label."""

    scene = build_scene(
        sources=(
            build_source("wf:text", "Text", {1: uuid4()}),
            build_source("wf:upscale", "Upscale", {2: uuid4()}),
        )
    )

    assert scene_has_completed_source_set(
        scene,
        source_key="wf:upscale",
        set_index=2,
    )
    assert scene_has_completed_source_label_set(
        scene,
        source_label="upscale",
        set_index=2,
    )
    assert source_label_for_key(scene, "wf:text") == "Text"
    assert source_labels_match("Upscale", "upscale")
    assert not source_labels_match("", "upscale")


def test_preview_slot_matches_completed_output_by_run_set_and_label() -> None:
    """Preview retirement should require matching scene run, set, and source label."""

    scene = build_scene(sources=(build_source("wf:final", "Upscale", {1: uuid4()}),))
    preview_slot = ScenePreviewSlot(
        scene_run_id="scene-run",
        generation_run_id="generation-run",
        scene_key="portrait",
        source_key="wf:preview",
        set_index=1,
        preview_id=uuid4(),
        source_label="upscale",
    )

    assert preview_slot_matches_completed_output(
        preview_slot,
        PreviewSlotKey(
            scene_run_id="scene-run",
            generation_run_id="generation-run",
            scene_key="portrait",
            source_key="wf:final",
            set_index=1,
        ),
        source_label="",
        scene=scene,
    )
    assert not preview_slot_matches_completed_output(
        preview_slot,
        PreviewSlotKey(
            scene_run_id="scene-run",
            generation_run_id="other-run",
            scene_key="portrait",
            source_key="wf:final",
            set_index=1,
        ),
        source_label="",
        scene=scene,
    )


def test_scene_preview_id_for_source_reuses_ids_per_slot() -> None:
    """Scene preview IDs should be stable for one run-scoped source slot."""

    preview_ids_by_scene_slot: dict[PreviewSlotKey, UUID] = {}

    preview_id = scene_preview_id_for_source(
        preview_ids_by_scene_slot,
        generation_run_id="generation-run",
        scene_run_id="scene-run",
        scene_key="portrait",
        source_key="wf:text",
        set_index=1,
    )
    reused_preview_id = scene_preview_id_for_source(
        preview_ids_by_scene_slot,
        generation_run_id="generation-run",
        scene_run_id="scene-run",
        scene_key="portrait",
        source_key="wf:text",
        set_index=1,
    )
    other_preview_id = scene_preview_id_for_source(
        preview_ids_by_scene_slot,
        generation_run_id="generation-run",
        scene_run_id="scene-run",
        scene_key="portrait",
        source_key="wf:upscale",
        set_index=1,
    )

    assert reused_preview_id == preview_id
    assert other_preview_id != preview_id
    assert (
        preview_ids_by_scene_slot[
            PreviewSlotKey(
                scene_run_id="scene-run",
                generation_run_id="generation-run",
                scene_key="portrait",
                source_key="wf:text",
                set_index=1,
            )
        ]
        == preview_id
    )

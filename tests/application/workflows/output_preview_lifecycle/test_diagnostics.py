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

"""Verify Output preview lifecycle diagnostic snapshots."""

from __future__ import annotations

from typing import cast
from uuid import uuid4

from substitute.application.workflows.output_preview_lifecycle_service import (
    PreviewSlotKey,
    ScenePreviewSlot,
    SourcePreviewSlotKey,
    preview_registry_snapshot,
)


def test_preview_registry_snapshot_reports_preview_lifecycle_diagnostics() -> None:
    """Preview diagnostics should expose source, scene, cache, and completed-slot state."""

    source_preview_id = uuid4()
    source_slot_preview_id = uuid4()
    scene_slot_preview_id = uuid4()
    accepted_scene_preview_id = uuid4()
    missing_preview_id = uuid4()
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

    snapshot = preview_registry_snapshot(
        source_preview_ids_by_key={"wf:text": source_preview_id},
        source_preview_ids_by_slot={source_slot: source_slot_preview_id},
        scene_preview_ids_by_slot={scene_slot: scene_slot_preview_id},
        scene_preview_slots_by_key={
            "portrait": ScenePreviewSlot(
                scene_run_id="scene-run",
                generation_run_id="generation-run",
                scene_key="portrait",
                source_key="wf:upscale",
                set_index=1,
                preview_id=accepted_scene_preview_id,
                source_label="Upscale",
            )
        },
        preview_images_by_id={
            source_preview_id: object(),
            source_slot_preview_id: object(),
            scene_slot_preview_id: object(),
        },
        completed_preview_slots={scene_slot},
        unscoped_preview_id=missing_preview_id,
    )

    assert snapshot["preview_registry_source_ids"] == (
        ("wf:text", str(source_preview_id)),
    )
    assert snapshot["preview_registry_source_fingerprints"] == (("wf:text", None),)
    assert snapshot["preview_registry_source_slot_ids"] == (
        ("scene-run", "portrait", "wf:text", 1, str(source_slot_preview_id)),
    )
    assert snapshot["preview_registry_scene_slot_ids"] == (
        ("scene-run", "portrait", "wf:upscale", 1, str(scene_slot_preview_id)),
    )
    assert snapshot["preview_registry_accepted_scene_slots"] == (
        (
            "portrait",
            "scene-run",
            "wf:upscale",
            "Upscale",
            1,
            str(accepted_scene_preview_id),
            None,
        ),
    )
    cached_ids = cast(tuple[str, ...], snapshot["preview_registry_cached_ids"])
    missing_ids = cast(tuple[str, ...], snapshot["preview_registry_missing_ids"])
    assert set(cached_ids) == {
        str(source_preview_id),
        str(source_slot_preview_id),
        str(scene_slot_preview_id),
    }
    assert set(missing_ids) == {
        str(accepted_scene_preview_id),
        str(missing_preview_id),
    }
    assert snapshot["preview_registry_completed_slots"] == (
        ("scene-run", "portrait", "wf:upscale", 1),
    )
    assert snapshot["preview_registry_total_cached_images"] == 3

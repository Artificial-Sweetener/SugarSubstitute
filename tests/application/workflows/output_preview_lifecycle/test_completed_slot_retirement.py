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

"""Verify completed-slot preview identity collection and retirement planning."""

from __future__ import annotations

from uuid import uuid4

from substitute.application.workflows.output_preview_lifecycle_service import (
    PreviewSlotKey,
    ScenePreviewSlot,
    SourcePreviewSlotKey,
    completed_slot_preview_retirement_plan,
    preview_ids_for_completed_slot,
)


from tests.application.workflows.output_preview_lifecycle.support import (
    build_scene,
    build_source,
)


def test_preview_ids_for_completed_slot_collects_matching_scene_and_source_ids() -> (
    None
):
    """Preview retirement should collect every preview ID tied to a final slot."""

    accepted_preview_id = uuid4()
    scene_preview_id = uuid4()
    source_slot_preview_id = uuid4()
    source_preview_id = uuid4()
    slot_key = PreviewSlotKey(
        scene_run_id="scene-run",
        generation_run_id="generation-run",
        scene_key="portrait",
        source_key="wf:upscale",
        set_index=1,
    )
    accepted_slot = ScenePreviewSlot(
        scene_run_id="scene-run",
        generation_run_id="generation-run",
        scene_key="portrait",
        source_key="wf:upscale",
        set_index=1,
        preview_id=accepted_preview_id,
        source_label="Upscale",
    )

    preview_ids = preview_ids_for_completed_slot(
        slot_key=slot_key,
        source_label="Upscale",
        accepted_slot=accepted_slot,
        scene=build_scene(sources=(build_source("wf:upscale", "Upscale", {}),)),
        scene_preview_ids_by_slot={slot_key: scene_preview_id},
        source_preview_ids_by_slot={
            SourcePreviewSlotKey(
                scene_run_id="scene-run",
                generation_run_id="generation-run",
                scene_key="portrait",
                source_key="wf:upscale",
                set_index=1,
            ): source_slot_preview_id,
        },
        source_preview_ids_by_key={"wf:upscale": source_preview_id},
    )

    assert set(preview_ids) == {
        accepted_preview_id,
        scene_preview_id,
        source_slot_preview_id,
        source_preview_id,
    }


def test_completed_slot_preview_retirement_plan_reports_context_and_preview_ids() -> (
    None
):
    """Completed-slot retirement should expose preview IDs and retirement context."""

    accepted_preview_id = uuid4()
    scene_preview_id = uuid4()
    source_preview_id = uuid4()
    slot_key = PreviewSlotKey(
        scene_run_id="scene-run",
        generation_run_id="generation-run",
        scene_key="portrait",
        source_key="wf:upscale",
        set_index=2,
    )
    accepted_slot = ScenePreviewSlot(
        scene_run_id="scene-run",
        generation_run_id="generation-run",
        scene_key="portrait",
        source_key="wf:preview-node",
        set_index=2,
        preview_id=accepted_preview_id,
        source_label="Upscale",
    )

    plan = completed_slot_preview_retirement_plan(
        slot_key=slot_key,
        source_label="Upscale",
        accepted_slot=accepted_slot,
        scene=build_scene(sources=(build_source("wf:upscale", "Upscale", {}),)),
        scene_preview_ids_by_slot={slot_key: scene_preview_id},
        source_preview_ids_by_slot={},
        source_preview_ids_by_key={"wf:upscale": source_preview_id},
    )

    assert set(plan.retire_preview_ids) == {
        accepted_preview_id,
        scene_preview_id,
        source_preview_id,
    }
    assert plan.scene_run_id == "scene-run"
    assert plan.scene_key == "portrait"
    assert plan.source_key == "wf:upscale"
    assert plan.set_index == 2

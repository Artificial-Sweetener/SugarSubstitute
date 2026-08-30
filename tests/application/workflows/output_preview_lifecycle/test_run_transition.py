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

"""Verify preview retirement and state changes across generation runs."""

from __future__ import annotations

from uuid import uuid4

from substitute.application.workflows.output_preview_lifecycle_service import (
    OutputCanvasRevisionCache,
    PreviewSlotKey,
    ScenePreviewSlot,
    SourcePreviewSlotKey,
    apply_preview_run_transition,
    completed_preview_slots_for_generation,
    preview_ids_for_run_transition,
    preview_run_transition_plan,
)


def test_preview_ids_for_run_transition_collects_all_known_preview_ids() -> None:
    """Run transitions should retire every source and scene preview identity."""

    source_preview_id = uuid4()
    source_slot_preview_id = uuid4()
    scene_slot_preview_id = uuid4()
    accepted_scene_preview_id = uuid4()

    preview_ids = preview_ids_for_run_transition(
        source_preview_ids_by_key={"wf:text": source_preview_id},
        source_preview_ids_by_slot={
            SourcePreviewSlotKey(
                scene_run_id="scene-run",
                generation_run_id="generation-run",
                scene_key="portrait",
                source_key="wf:text",
                set_index=1,
            ): source_slot_preview_id
        },
        scene_preview_ids_by_slot={
            PreviewSlotKey(
                scene_run_id="scene-run",
                generation_run_id="generation-run",
                scene_key="portrait",
                source_key="wf:upscale",
                set_index=1,
            ): scene_slot_preview_id
        },
        scene_preview_slots_by_key={
            "portrait": ScenePreviewSlot(
                scene_run_id="scene-run",
                generation_run_id="generation-run",
                scene_key="portrait",
                source_key="wf:upscale",
                set_index=1,
                preview_id=accepted_scene_preview_id,
            )
        },
    )

    assert set(preview_ids) == {
        source_preview_id,
        source_slot_preview_id,
        scene_slot_preview_id,
        accepted_scene_preview_id,
    }


def test_completed_preview_slots_for_generation_keeps_only_matching_run() -> None:
    """Run transitions should retain completed slots only for the new generation."""

    retained_slot = PreviewSlotKey(
        scene_run_id="scene-run",
        generation_run_id="generation-run-b",
        scene_key="portrait",
        source_key="wf:text",
        set_index=1,
    )
    stale_slot = PreviewSlotKey(
        scene_run_id="scene-run",
        generation_run_id="generation-run-a",
        scene_key="portrait",
        source_key="wf:upscale",
        set_index=1,
    )

    assert completed_preview_slots_for_generation(
        {retained_slot, stale_slot},
        generation_run_id="generation-run-b",
    ) == {retained_slot}


def test_preview_run_transition_plan_initializes_first_active_run() -> None:
    """First preview run should update active identity without retiring previews."""

    retained_slot = PreviewSlotKey(
        scene_run_id="scene-run",
        generation_run_id="generation-run",
        scene_key="portrait",
        source_key="wf:text",
        set_index=1,
    )

    plan = preview_run_transition_plan(
        active_generation_run_id="",
        active_scene_run_id=None,
        next_generation_run_id="generation-run",
        next_scene_run_id="scene-run",
        completed_preview_slots={retained_slot},
        source_preview_ids_by_key={"wf:text": uuid4()},
        source_preview_ids_by_slot={},
        scene_preview_ids_by_slot={},
        scene_preview_slots_by_key={},
    )

    assert plan is not None
    assert plan.retire_preview_ids == ()
    assert plan.retire_scene_run_id == ""
    assert plan.retained_completed_slots == frozenset({retained_slot})
    assert plan.next_generation_run_id == "generation-run"
    assert plan.next_scene_run_id == "scene-run"


def test_preview_run_transition_plan_ignores_current_generation_run() -> None:
    """Accepting the current generation run should not mutate preview lifecycle state."""

    assert (
        preview_run_transition_plan(
            active_generation_run_id="generation-run",
            active_scene_run_id="scene-run",
            next_generation_run_id="generation-run",
            next_scene_run_id="scene-run-next",
            completed_preview_slots=(),
            source_preview_ids_by_key={},
            source_preview_ids_by_slot={},
            scene_preview_ids_by_slot={},
            scene_preview_slots_by_key={},
        )
        is None
    )


def test_preview_run_transition_plan_retires_stale_run_previews() -> None:
    """New generation runs should retire stale preview IDs and retain matching slots."""

    source_preview_id = uuid4()
    scene_preview_id = uuid4()
    accepted_preview_id = uuid4()
    retained_slot = PreviewSlotKey(
        scene_run_id="scene-run-b",
        generation_run_id="generation-run-b",
        scene_key="portrait",
        source_key="wf:text",
        set_index=1,
    )
    stale_slot = PreviewSlotKey(
        scene_run_id="scene-run-a",
        generation_run_id="generation-run-a",
        scene_key="portrait",
        source_key="wf:upscale",
        set_index=1,
    )

    plan = preview_run_transition_plan(
        active_generation_run_id="generation-run-a",
        active_scene_run_id="scene-run-a",
        next_generation_run_id="generation-run-b",
        next_scene_run_id="scene-run-b",
        completed_preview_slots={retained_slot, stale_slot},
        source_preview_ids_by_key={"wf:text": source_preview_id},
        source_preview_ids_by_slot={},
        scene_preview_ids_by_slot={stale_slot: scene_preview_id},
        scene_preview_slots_by_key={
            "portrait": ScenePreviewSlot(
                scene_run_id="scene-run-a",
                generation_run_id="generation-run-a",
                scene_key="portrait",
                source_key="wf:upscale",
                set_index=1,
                preview_id=accepted_preview_id,
            )
        },
    )

    assert plan is not None
    assert set(plan.retire_preview_ids) == {
        source_preview_id,
        scene_preview_id,
        accepted_preview_id,
    }
    assert plan.retire_scene_run_id == "generation-run-a"
    assert plan.retained_completed_slots == frozenset({retained_slot})
    assert plan.next_generation_run_id == "generation-run-b"
    assert plan.next_scene_run_id == "scene-run-b"


def test_apply_preview_run_transition_updates_cache_state() -> None:
    """Preview transition application should stay in the lifecycle service."""

    cache = OutputCanvasRevisionCache()
    retained_slot = PreviewSlotKey(
        scene_run_id="scene-run-b",
        generation_run_id="generation-run-b",
        scene_key="portrait",
        source_key="wf:text",
        set_index=1,
    )
    stale_slot = PreviewSlotKey(
        scene_run_id="scene-run-a",
        generation_run_id="generation-run-a",
        scene_key="portrait",
        source_key="wf:upscale",
        set_index=1,
    )
    completed_slots = {retained_slot, stale_slot}

    plan = preview_run_transition_plan(
        active_generation_run_id="generation-run-a",
        active_scene_run_id="scene-run-a",
        next_generation_run_id="generation-run-b",
        next_scene_run_id="scene-run-b",
        completed_preview_slots=completed_slots,
        source_preview_ids_by_key={},
        source_preview_ids_by_slot={},
        scene_preview_ids_by_slot={},
        scene_preview_slots_by_key={},
    )

    assert plan is not None

    apply_preview_run_transition(
        cache,
        plan,
        completed_preview_slots=completed_slots,
    )

    assert completed_slots == {retained_slot}
    assert cache.active_preview_generation_run_id == "generation-run-b"
    assert cache.active_preview_scene_run_id == "scene-run-b"

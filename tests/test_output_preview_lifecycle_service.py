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

"""Verify pure Output preview lifecycle decisions."""

from __future__ import annotations

from typing import cast
from uuid import UUID, uuid4

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasProjection,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_canvas_session import (
    OutputCanvasSession,
    bind_output_canvas_session,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewLane,
    OutputPreviewLaneKey,
    OutputPreviewRegistry,
)
from substitute.application.workflows.output_preview_lifecycle_service import (
    OutputCanvasRevisionCache,
    PreviewSlotKey,
    ScenePreviewSlot,
    SourcePreviewSlotKey,
    apply_preview_retirement_plan,
    apply_preview_run_transition,
    completed_slot_preview_retirement_plan,
    completed_preview_slots_for_generation,
    consume_final_output_preview_retirement,
    final_output_preview_retirement,
    output_revision_cache_binding,
    preview_ids_for_completed_slot,
    preview_ids_for_run_transition,
    preview_registry_snapshot,
    preview_retirement_plan,
    preview_run_transition_plan,
    preview_slot_matches_completed_output,
    preview_slot_for_scene,
    preview_slot_is_completed,
    scene_group_without_preview,
    scene_has_completed_source_label_set,
    scene_has_completed_source_set,
    scene_preview_id_for_source,
    scene_preview_matches_representative,
    source_is_after,
    source_is_new_for_scene,
    source_label_for_key,
    source_labels_match,
)
from substitute.domain.workflow import (
    CanvasSessionBoundary,
    CanvasSessionRevision,
    ImageMeta,
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

    scene = _scene(
        sources=(
            _source("wf:text", "Text", {1: uuid4()}),
            _source("wf:upscale", "Upscale", {2: uuid4()}),
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

    scene = _scene(sources=(_source("wf:final", "Upscale", {1: uuid4()}),))
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


def test_representative_preview_prefers_later_or_new_sources() -> None:
    """Scene overview previews should advance to later or newly introduced sources."""

    scene = _scene(
        sources=(
            _source("wf:text", "Text", {1: uuid4()}),
            _source("wf:upscale", "Upscale", {1: uuid4()}),
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

    scene = _scene(
        sources=(
            _source("wf:text", "Text", {1: uuid4()}),
            _source("wf:upscale", "Upscale", {}),
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
    scene = _scene(
        scene_run_id="scene-run",
        sources=(_source("wf:upscale", "Upscale", {2: uuid4()}),),
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

    prior_generation_scene = _scene(
        scene_run_id="scene-run",
        sources=(
            _source(
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
    scene = _scene(
        sources=(
            _source("wf:text", "Text", {1: uuid4()}),
            _source("wf:upscale", "Upscale", {}),
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
        scene=_scene(sources=(_source("wf:upscale", "Upscale", {}),)),
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
        scene=_scene(sources=(_source("wf:upscale", "Upscale", {}),)),
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


def test_revision_cache_projects_registry_lanes_to_preview_maps() -> None:
    """Revision cache should expose registry-owned source and scene preview state."""

    source_preview_id = uuid4()
    scene_preview_id = uuid4()
    source_image = object()
    scene_image = object()
    registry = OutputPreviewRegistry()
    registry.store_accepted_lane(
        OutputPreviewLane(
            key=OutputPreviewLaneKey.source(
                workflow_id="workflow",
                generation_run_id="generation-run",
                prompt_id="prompt",
                source_key="wf:text",
                scene_run_id="scene-run",
                scene_key="portrait",
            ),
            preview_id=source_preview_id,
            image=source_image,
            source_label="Text",
            client_id="client",
            session_revision=CanvasSessionRevision(1),
        )
    )
    registry.store_accepted_lane(
        OutputPreviewLane(
            key=OutputPreviewLaneKey.scene(
                workflow_id="workflow",
                generation_run_id="generation-run",
                prompt_id="prompt",
                source_key="wf:upscale",
                scene_run_id="scene-run",
                scene_key="portrait",
            ),
            preview_id=scene_preview_id,
            image=scene_image,
            source_label="Upscale",
            client_id="client",
            session_revision=CanvasSessionRevision(1),
            scene_title="Portrait",
            scene_order=2,
            scene_count=3,
            accepted_for_overview=True,
        )
    )

    cache = OutputCanvasRevisionCache(
        registry=registry,
        active_preview_generation_run_id="generation-run",
        active_preview_scene_run_id="scene-run",
    )

    assert cache.preview_images_by_id == {
        source_preview_id: source_image,
        scene_preview_id: scene_image,
    }
    assert cache.preview_ids_by_source_key == {"wf:text": source_preview_id}
    assert cache.preview_ids_by_source_slot == {
        SourcePreviewSlotKey(
            scene_run_id="scene-run",
            generation_run_id="generation-run",
            scene_key="portrait",
            source_key="wf:text",
            set_index=1,
        ): source_preview_id
    }
    assert cache.preview_ids_by_scene_slot == {
        PreviewSlotKey(
            scene_run_id="scene-run",
            generation_run_id="generation-run",
            scene_key="portrait",
            source_key="wf:upscale",
            set_index=1,
        ): scene_preview_id
    }
    assert cache.scene_preview_slots_by_key == {
        "portrait": ScenePreviewSlot(
            scene_run_id="scene-run",
            generation_run_id="generation-run",
            scene_key="portrait",
            source_key="wf:upscale",
            set_index=1,
            preview_id=scene_preview_id,
            source_label="Upscale",
        )
    }
    assert cache.preview_scene_groups_by_key["portrait"].preview_image_id == (
        scene_preview_id
    )
    assert cache.preview_labels_by_source_key == {"wf:text": "Text"}
    assert cache.preview_images_by_source_key == {"wf:text": source_image}
    assert cache.completed_preview_slots == set()
    assert cache.active_preview_generation_run_id == "generation-run"
    assert cache.active_preview_scene_run_id == "scene-run"


def test_output_revision_cache_binding_ignores_current_session_revision() -> None:
    """Revision cache binding should be a no-op for the current session revision."""

    registry = OutputPreviewRegistry()
    session = _session_for_projection(
        OutputCanvasProjection(
            sources=(),
            active_source_key=None,
            active_set_index=1,
            active_uuid=None,
            set_count=0,
        )
    )

    binding = output_revision_cache_binding(
        registry,
        session,
        current_cache_key=(session.workflow_id.value, session.revision.value),
    )

    assert binding is None


def test_output_revision_cache_binding_scopes_cache_to_new_session_revision() -> None:
    """Revision cache binding should reset cache reads to the new Output session."""

    preview_id = uuid4()
    preview = object()
    registry = OutputPreviewRegistry()
    registry.store_accepted_lane(
        OutputPreviewLane(
            key=OutputPreviewLaneKey.source(
                workflow_id="old-wf",
                generation_run_id="run-1",
                prompt_id="prompt-1",
                source_key="old-wf:node",
            ),
            preview_id=preview_id,
            image=preview,
            source_label="Old",
            client_id="client-1",
            session_revision=CanvasSessionRevision(1),
        )
    )
    session = _session_for_projection(
        OutputCanvasProjection(
            sources=(),
            active_source_key=None,
            active_set_index=1,
            active_uuid=None,
            set_count=0,
        ),
        workflow_id="new-wf",
    )

    binding = output_revision_cache_binding(
        registry,
        session,
        current_cache_key=("old-wf", 1),
    )

    assert binding is not None
    assert binding.cache_key == (session.workflow_id.value, session.revision.value)
    assert binding.cache.session is session
    assert binding.cache.preview_images_by_id == {}
    assert registry.images_by_id() == {preview_id: preview}


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


def test_scene_group_without_preview_preserves_final_scene_metadata() -> None:
    """Retired scene previews should preserve final output and representative metadata."""

    final_id = uuid4()
    preview_id = uuid4()
    scene = _scene(
        sources=(_source("wf:text", "Text", {1: final_id}),),
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
    source = _source("wf:text", "Text", {1: final_id})

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
            "portrait": _scene(
                sources=(source,),
                primary_image_id=final_id,
                preview_image_id=preview_id,
                representative_source_key="wf:text",
                representative_set_index=1,
            ),
            "draft": _scene(
                sources=(),
                scene_key="draft",
                preview_image_id=preview_id,
            ),
        },
        base_scene_groups_by_key={
            "fallback": _scene(
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
    updated_scene = _scene(
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
            "portrait": _scene(
                sources=(),
                primary_image_id=final_id,
                preview_image_id=preview_id,
                representative_source_key="wf:text",
            ),
            "draft": _scene(sources=(), scene_key="draft", preview_image_id=preview_id),
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
        "portrait": _scene(
            sources=(),
            primary_image_id=final_id,
            preview_image_id=preview_id,
            representative_source_key="wf:text",
        ),
        "draft": _scene(sources=(), scene_key="draft", preview_image_id=preview_id),
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


def test_final_output_preview_retirement_returns_completed_slot_command() -> None:
    """Final-output selection should expose the preview slot it supersedes."""

    final_id = uuid4()
    metadata = ImageMeta(
        workflow_name="Workflow",
        cube_name="Upscale",
        image_number=1,
        suffix="",
        path="E:/out.png",
        source_key="wf:upscale",
        source_label="Upscale",
        generation_run_id="generation-run",
        scene_run_id="scene-run",
        scene_key="portrait",
    )

    retirement = final_output_preview_retirement(
        image_id=final_id,
        pending_final_preview_retire_ids={final_id},
        source_key="wf:upscale",
        image_meta=metadata,
        set_index=2,
    )

    assert retirement is not None
    assert retirement.slot_key == PreviewSlotKey(
        scene_run_id="scene-run",
        generation_run_id="generation-run",
        scene_key="portrait",
        source_key="wf:upscale",
        set_index=2,
    )
    assert retirement.source_label == "Upscale"


def test_consume_final_output_preview_retirement_removes_pending_id() -> None:
    """Pending final-output retirements should be consumed with their command."""

    final_id = uuid4()
    other_id = uuid4()
    pending_ids = {final_id, other_id}
    metadata = ImageMeta(
        workflow_name="Workflow",
        cube_name="Upscale",
        image_number=1,
        suffix="",
        path="E:/out.png",
        source_key="wf:upscale",
        source_label="Upscale",
        generation_run_id="generation-run",
        scene_run_id="scene-run",
        scene_key="portrait",
    )

    retirement = consume_final_output_preview_retirement(
        image_id=final_id,
        pending_final_preview_retire_ids=pending_ids,
        source_key="wf:upscale",
        image_meta=metadata,
        set_index=2,
    )

    assert retirement is not None
    assert retirement.slot_key == PreviewSlotKey(
        scene_run_id="scene-run",
        generation_run_id="generation-run",
        scene_key="portrait",
        source_key="wf:upscale",
        set_index=2,
    )
    assert pending_ids == {other_id}


def test_final_output_preview_retirement_ignores_non_pending_output() -> None:
    """Final-output selection should not retire previews unless the final is pending."""

    metadata = ImageMeta(
        workflow_name="Workflow",
        cube_name="Upscale",
        image_number=1,
        suffix="",
        path="E:/out.png",
        source_key="wf:upscale",
        source_label="Upscale",
        generation_run_id="generation-run",
        scene_run_id="scene-run",
        scene_key="portrait",
    )

    assert (
        final_output_preview_retirement(
            image_id=uuid4(),
            pending_final_preview_retire_ids={uuid4()},
            source_key="wf:upscale",
            image_meta=metadata,
            set_index=2,
        )
        is None
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


def _scene(
    *,
    sources: tuple[OutputCanvasSourceGroup, ...],
    scene_key: str = "portrait",
    scene_run_id: str = "scene-run",
    primary_image_id: UUID | None = None,
    preview_image_id: UUID | None = None,
    representative_source_key: str | None = None,
    representative_set_index: int | None = None,
    status: str = "completed",
) -> OutputCanvasSceneGroup:
    """Return one scene group for lifecycle tests."""

    return OutputCanvasSceneGroup(
        scene_run_id=scene_run_id,
        scene_key=scene_key,
        title=scene_key.title(),
        order=0,
        sources=sources,
        preview_image_id=preview_image_id,
        primary_image_id=primary_image_id,
        representative_source_key=representative_source_key,
        representative_set_index=representative_set_index,
        status=status,
    )


def _session_for_projection(
    projection: OutputCanvasProjection,
    *,
    workflow_id: str = "wf",
) -> OutputCanvasSession:
    """Return an Output session wrapper for lifecycle tests."""

    return bind_output_canvas_session(
        CanvasSessionBoundary(),
        workflow_id=workflow_id,
        projection=projection,
        image_metadata_lookup={},
    )


def _source(
    source_key: str,
    label: str,
    images_by_set: dict[int, UUID],
    *,
    generation_run_id: str = "",
) -> OutputCanvasSourceGroup:
    """Return one source group with placeholder image metadata."""

    return OutputCanvasSourceGroup(
        source_key=source_key,
        label=label,
        images_by_set={
            set_index: OutputCanvasImageItem(
                image_id=image_id,
                image_meta=_meta(generation_run_id=generation_run_id),
                set_index=set_index,
            )
            for set_index, image_id in images_by_set.items()
        },
    )


def _meta(*, generation_run_id: str = "") -> ImageMeta:
    """Return minimal image metadata for lifecycle source fixtures."""

    return ImageMeta(
        workflow_name="Workflow",
        cube_name="Output",
        image_number=1,
        suffix="",
        path="E:/out.png",
        generation_run_id=generation_run_id,
    )

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

"""Resolve Output preview lifecycle identities without presentation dependencies."""

from __future__ import annotations

from collections.abc import Container, Iterable, Mapping, MutableMapping
from dataclasses import dataclass, field
from uuid import UUID
from uuid import uuid4

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasSceneGroup,
)
from substitute.application.workflows.output_canvas_session import OutputCanvasSession
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewLane,
    OutputPreviewLanePlacement,
    OutputPreviewRegistry,
)
from substitute.domain.workflow import ImageMeta


@dataclass(frozen=True, slots=True)
class ScenePreviewSlot:
    """Describe the transient preview slot currently representing one scene."""

    scene_run_id: str
    scene_key: str
    source_key: str
    set_index: int
    preview_id: UUID
    generation_run_id: str = ""
    source_label: str = ""

    def source_set(self) -> tuple[str, int]:
        """Return the source/set identity used for exact preview clearing."""

        return self.source_key, self.set_index

    def preview_key(self) -> "PreviewSlotKey":
        """Return the completed-slot key represented by this preview."""

        return PreviewSlotKey(
            scene_run_id=self.scene_run_id,
            generation_run_id=self.generation_run_id,
            scene_key=self.scene_key,
            source_key=self.source_key,
            set_index=self.set_index,
        )


@dataclass(frozen=True, slots=True)
class PreviewSlotKey:
    """Identify one run-scoped scene/source preview slot."""

    scene_run_id: str
    scene_key: str
    source_key: str
    set_index: int
    generation_run_id: str = ""


@dataclass(frozen=True, slots=True)
class SourcePreviewSlotKey:
    """Identify one scene-aware source preview slot."""

    scene_run_id: str
    scene_key: str
    source_key: str
    set_index: int
    generation_run_id: str = ""


@dataclass(slots=True)
class OutputCanvasRevisionCache:
    """Expose registry-owned preview lanes through projection-cache helpers."""

    registry: OutputPreviewRegistry = field(default_factory=OutputPreviewRegistry)
    session: OutputCanvasSession | None = None
    pending_final_preview_retire_ids: set[UUID] = field(default_factory=set)
    active_preview_generation_run_id: str = ""
    active_preview_scene_run_id: str | None = None

    def _lanes(self) -> tuple[OutputPreviewLane, ...]:
        """Return lanes visible to the bound Output session."""

        if self.session is not None:
            return self.registry.lanes_for_session(self.session)
        return self.registry.lanes_for_session_like()

    @property
    def preview_images_by_id(self) -> dict[UUID, object]:
        """Return preview payloads from registry-owned lanes."""

        return {lane.preview_id: lane.image for lane in self._lanes()}

    @property
    def preview_ids_by_source_key(self) -> dict[str, UUID]:
        """Return source preview ids from registry-owned lanes."""

        return {
            lane.key.source_key: lane.preview_id
            for lane in self._lanes()
            if lane.key.placement is OutputPreviewLanePlacement.SOURCE
        }

    @property
    def preview_ids_by_source_slot(self) -> dict[SourcePreviewSlotKey, UUID]:
        """Return scene-aware source preview ids from registry-owned lanes."""

        return {
            SourcePreviewSlotKey(
                scene_run_id=lane.key.scene_run_id or "",
                generation_run_id=lane.key.generation_run_id,
                scene_key=lane.key.scene_key or "",
                source_key=lane.key.source_key,
                set_index=1,
            ): lane.preview_id
            for lane in self._lanes()
            if lane.key.placement is OutputPreviewLanePlacement.SOURCE
            and lane.key.scene_run_id is not None
        }

    @property
    def preview_ids_by_scene_slot(self) -> dict[PreviewSlotKey, UUID]:
        """Return scene preview ids from registry-owned lanes."""

        return {
            PreviewSlotKey(
                scene_run_id=lane.key.scene_run_id or "",
                generation_run_id=lane.key.generation_run_id,
                scene_key=lane.key.scene_key or "",
                source_key=lane.key.source_key,
                set_index=1,
            ): lane.preview_id
            for lane in self._lanes()
            if lane.key.placement is OutputPreviewLanePlacement.SCENE
        }

    @property
    def preview_scene_groups_by_key(self) -> dict[str, OutputCanvasSceneGroup]:
        """Return preview scene groups from registry-owned lanes."""

        return self.registry.preview_scene_groups(self.session)

    @property
    def scene_preview_slots_by_key(self) -> dict[str, ScenePreviewSlot]:
        """Return accepted scene preview slots from registry-owned lanes."""

        return {
            scene_key: ScenePreviewSlot(
                scene_run_id=lane.key.scene_run_id or "",
                generation_run_id=lane.key.generation_run_id,
                scene_key=scene_key,
                source_key=lane.key.source_key,
                set_index=1,
                preview_id=lane.preview_id,
                source_label=lane.source_label,
            )
            for scene_key, lane in {
                lane.key.scene_key: lane
                for lane in self._lanes()
                if lane.key.placement is OutputPreviewLanePlacement.SCENE
                and lane.key.scene_key is not None
                and lane.accepted_for_overview
            }.items()
        }

    @property
    def completed_preview_slots(self) -> set[PreviewSlotKey]:
        """Return completed preview slot diagnostics."""

        return set()

    @property
    def preview_labels_by_source_key(self) -> dict[str, str]:
        """Return source labels from registry-owned source lanes."""

        return {
            lane.key.source_key: lane.source_label
            for lane in self._lanes()
            if lane.key.placement is OutputPreviewLanePlacement.SOURCE
        }

    @property
    def preview_images_by_source_key(self) -> dict[str, object]:
        """Return source images from registry-owned source lanes."""

        return {
            lane.key.source_key: lane.image
            for lane in self._lanes()
            if lane.key.placement is OutputPreviewLanePlacement.SOURCE
        }


@dataclass(frozen=True, slots=True)
class OutputCanvasRevisionCacheBinding:
    """Describe a new revision cache binding for one Output projection session."""

    cache_key: tuple[str, int]
    cache: OutputCanvasRevisionCache


def output_revision_cache_binding(
    registry: OutputPreviewRegistry,
    session: OutputCanvasSession,
    *,
    current_cache_key: object,
) -> OutputCanvasRevisionCacheBinding | None:
    """Return a new revision cache binding when the Output session changed."""

    cache_key = (session.workflow_id.value, session.revision.value)
    if current_cache_key == cache_key:
        return None
    return OutputCanvasRevisionCacheBinding(
        cache_key=cache_key,
        cache=OutputCanvasRevisionCache(registry, session),
    )


@dataclass(frozen=True, slots=True)
class FinalOutputPreviewRetirement:
    """Describe the preview slot retired by selecting a final output."""

    slot_key: PreviewSlotKey
    source_label: str


@dataclass(frozen=True, slots=True)
class CompletedSlotPreviewRetirementPlan:
    """Describe previews retired by one completed final-output slot."""

    retire_preview_ids: tuple[UUID, ...]
    scene_run_id: str
    scene_key: str
    source_key: str
    set_index: int


@dataclass(frozen=True, slots=True)
class PreviewRunTransitionPlan:
    """Describe preview lifecycle changes required for a new generation run."""

    retire_preview_ids: tuple[UUID, ...]
    retire_scene_run_id: str
    retained_completed_slots: frozenset[PreviewSlotKey]
    next_generation_run_id: str
    next_scene_run_id: str | None


@dataclass(frozen=True, slots=True)
class PreviewRetirementPlan:
    """Describe registry mutations required to retire one preview image."""

    removed_source_keys: tuple[str, ...]
    removed_source_slots: tuple[SourcePreviewSlotKey, ...]
    removed_scene_slots: tuple[PreviewSlotKey, ...]
    removed_accepted_scene_keys: tuple[str, ...]
    removed_preview_scene_group_keys: tuple[str, ...]
    updated_preview_scene_groups: tuple[tuple[str, OutputCanvasSceneGroup], ...]


def scene_has_completed_source_set(
    scene: OutputCanvasSceneGroup,
    *,
    source_key: str,
    set_index: int,
    generation_run_id: str = "",
) -> bool:
    """Return whether a scene has a completed final output for one slot."""

    return any(
        source.source_key == source_key
        and (item := source.images_by_set.get(set_index)) is not None
        and (
            not generation_run_id
            or item.image_meta.generation_run_id == generation_run_id
        )
        for source in scene.sources
    )


def scene_has_completed_source_label_set(
    scene: OutputCanvasSceneGroup,
    *,
    source_label: str,
    set_index: int,
) -> bool:
    """Return whether a scene has a final output for one source label/set."""

    if not source_label:
        return False
    return any(
        source_labels_match(source.label, source_label)
        and set_index in source.images_by_set
        for source in scene.sources
    )


def preview_slot_matches_completed_output(
    preview_slot: ScenePreviewSlot,
    completed_slot_key: PreviewSlotKey,
    *,
    source_label: str,
    scene: OutputCanvasSceneGroup | None,
) -> bool:
    """Return whether a final output supersedes a preview-node source slot."""

    if preview_slot.scene_key != completed_slot_key.scene_key:
        return False
    if preview_slot.scene_run_id != completed_slot_key.scene_run_id:
        return False
    if (
        preview_slot.generation_run_id
        and completed_slot_key.generation_run_id
        and preview_slot.generation_run_id != completed_slot_key.generation_run_id
    ):
        return False
    if preview_slot.set_index != completed_slot_key.set_index:
        return False
    completed_source_label = source_label or (
        source_label_for_key(scene, completed_slot_key.source_key)
        if scene is not None
        else ""
    )
    return source_labels_match(preview_slot.source_label, completed_source_label)


def source_label_for_key(scene: OutputCanvasSceneGroup, source_key: str) -> str:
    """Return the display label for a completed scene source key."""

    for source in scene.sources:
        if source.source_key == source_key:
            return source.label
    return ""


def source_labels_match(left: str, right: str) -> bool:
    """Return whether two output labels describe the same canvas source."""

    return bool(left and right and left.casefold() == right.casefold())


def scene_preview_matches_representative(
    *,
    scene: OutputCanvasSceneGroup | None,
    current_slot: ScenePreviewSlot | None,
    source_key: str,
) -> bool:
    """Return whether a preview should represent its scene overview tile."""

    if not source_key:
        return current_slot is None
    if current_slot is not None:
        if source_key == current_slot.source_key:
            return True
        if scene is None:
            return False
        if source_is_after(scene, source_key, current_slot.source_key):
            return True
        scene_source_keys = tuple(source.source_key for source in scene.sources)
        return source_is_new_for_scene(scene, source_key) and (
            current_slot.source_key == scene.representative_source_key
            or current_slot.source_key not in scene_source_keys
        )
    representative_source_key = (
        scene.representative_source_key if scene is not None else None
    )
    if representative_source_key:
        if source_key == representative_source_key:
            return True
        if scene is not None and source_is_after(
            scene,
            source_key,
            representative_source_key,
        ):
            return True
        if scene is not None and source_is_new_for_scene(scene, source_key):
            return True
        return False
    return True


def preview_slot_is_completed(
    *,
    slot_key: PreviewSlotKey,
    scene: OutputCanvasSceneGroup | None,
    completed_preview_slots: Container[PreviewSlotKey],
) -> bool:
    """Return whether a preview slot already has a final output."""

    if slot_key.scene_run_id and slot_key in completed_preview_slots:
        return True
    if scene is None:
        return False
    if (
        scene.scene_run_id
        and slot_key.scene_run_id
        and scene.scene_run_id != slot_key.scene_run_id
    ):
        return False
    return scene_has_completed_source_set(
        scene,
        source_key=slot_key.source_key,
        set_index=slot_key.set_index,
        generation_run_id=slot_key.generation_run_id,
    )


def preview_slot_for_scene(
    *,
    scene: OutputCanvasSceneGroup,
    preview_slot: ScenePreviewSlot | None,
    cached_preview_ids: Container[UUID],
    completed_preview_slots: Container[PreviewSlotKey],
) -> ScenePreviewSlot | None:
    """Return the accepted scene overview preview slot when still valid."""

    if preview_slot is None:
        return None
    if preview_slot.preview_id not in cached_preview_ids:
        return None
    if preview_slot_is_completed(
        slot_key=preview_slot.preview_key(),
        scene=scene,
        completed_preview_slots=completed_preview_slots,
    ):
        return None
    if scene_has_completed_source_set(
        scene,
        source_key=preview_slot.source_key,
        set_index=preview_slot.set_index,
        generation_run_id=preview_slot.generation_run_id,
    ):
        return None
    if scene.primary_image_id is None:
        return preview_slot
    if scene.representative_source_key is None:
        return preview_slot
    if preview_slot.source_key == scene.representative_source_key:
        return preview_slot
    if source_is_after(
        scene,
        preview_slot.source_key,
        scene.representative_source_key,
    ):
        return preview_slot
    if source_is_new_for_scene(scene, preview_slot.source_key):
        return preview_slot
    return None


def preview_ids_for_completed_slot(
    *,
    slot_key: PreviewSlotKey,
    source_label: str = "",
    accepted_slot: ScenePreviewSlot | None,
    scene: OutputCanvasSceneGroup | None,
    scene_preview_ids_by_slot: Mapping[PreviewSlotKey, UUID],
    source_preview_ids_by_slot: Mapping[SourcePreviewSlotKey, UUID],
    source_preview_ids_by_key: Mapping[str, UUID],
) -> tuple[UUID, ...]:
    """Return preview IDs that should retire for one completed final slot."""

    preview_ids: set[UUID] = set()
    if accepted_slot is not None and (
        accepted_slot.preview_key() == slot_key
        or preview_slot_matches_completed_output(
            accepted_slot,
            slot_key,
            source_label=source_label,
            scene=scene,
        )
    ):
        preview_ids.add(accepted_slot.preview_id)
    scene_preview_id = scene_preview_ids_by_slot.get(slot_key)
    if scene_preview_id is not None:
        preview_ids.add(scene_preview_id)
    source_preview_id = source_preview_ids_by_slot.get(
        SourcePreviewSlotKey(
            scene_run_id=slot_key.scene_run_id,
            generation_run_id=slot_key.generation_run_id,
            scene_key=slot_key.scene_key,
            source_key=slot_key.source_key,
            set_index=slot_key.set_index,
        ),
    )
    if source_preview_id is not None:
        preview_ids.add(source_preview_id)
    source_preview_id = source_preview_ids_by_key.get(slot_key.source_key)
    if source_preview_id is not None:
        preview_ids.add(source_preview_id)
    return tuple(preview_ids)


def completed_slot_preview_retirement_plan(
    *,
    slot_key: PreviewSlotKey,
    source_label: str = "",
    accepted_slot: ScenePreviewSlot | None,
    scene: OutputCanvasSceneGroup | None,
    scene_preview_ids_by_slot: Mapping[PreviewSlotKey, UUID],
    source_preview_ids_by_slot: Mapping[SourcePreviewSlotKey, UUID],
    source_preview_ids_by_key: Mapping[str, UUID],
) -> CompletedSlotPreviewRetirementPlan:
    """Return preview-retirement commands for one completed final-output slot."""

    return CompletedSlotPreviewRetirementPlan(
        retire_preview_ids=preview_ids_for_completed_slot(
            slot_key=slot_key,
            source_label=source_label,
            accepted_slot=accepted_slot,
            scene=scene,
            scene_preview_ids_by_slot=scene_preview_ids_by_slot,
            source_preview_ids_by_slot=source_preview_ids_by_slot,
            source_preview_ids_by_key=source_preview_ids_by_key,
        ),
        scene_run_id=slot_key.scene_run_id,
        scene_key=slot_key.scene_key,
        source_key=slot_key.source_key,
        set_index=slot_key.set_index,
    )


def preview_ids_for_run_transition(
    *,
    source_preview_ids_by_key: Mapping[str, UUID],
    source_preview_ids_by_slot: Mapping[SourcePreviewSlotKey, UUID],
    scene_preview_ids_by_slot: Mapping[PreviewSlotKey, UUID],
    scene_preview_slots_by_key: Mapping[str, ScenePreviewSlot],
) -> tuple[UUID, ...]:
    """Return preview IDs that should retire when accepting a new run."""

    preview_ids = set(source_preview_ids_by_key.values())
    preview_ids.update(source_preview_ids_by_slot.values())
    preview_ids.update(scene_preview_ids_by_slot.values())
    preview_ids.update(slot.preview_id for slot in scene_preview_slots_by_key.values())
    return tuple(preview_ids)


def completed_preview_slots_for_generation(
    completed_preview_slots: Iterable[PreviewSlotKey],
    *,
    generation_run_id: str,
) -> set[PreviewSlotKey]:
    """Return completed preview slots that still belong to one generation run."""

    return {
        slot
        for slot in completed_preview_slots
        if slot.generation_run_id == generation_run_id
    }


def preview_run_transition_plan(
    *,
    active_generation_run_id: str,
    active_scene_run_id: str | None,
    next_generation_run_id: str,
    next_scene_run_id: str | None,
    completed_preview_slots: Iterable[PreviewSlotKey],
    source_preview_ids_by_key: Mapping[str, UUID],
    source_preview_ids_by_slot: Mapping[SourcePreviewSlotKey, UUID],
    scene_preview_ids_by_slot: Mapping[PreviewSlotKey, UUID],
    scene_preview_slots_by_key: Mapping[str, ScenePreviewSlot],
) -> PreviewRunTransitionPlan | None:
    """Return preview lifecycle changes for accepting a new generation run."""

    active_run_id = active_generation_run_id or active_scene_run_id or ""
    if active_run_id == next_generation_run_id:
        return None
    if not active_run_id:
        retained_completed_slots = frozenset(completed_preview_slots)
        retire_preview_ids: tuple[UUID, ...] = ()
    else:
        retained_completed_slots = frozenset(
            completed_preview_slots_for_generation(
                completed_preview_slots,
                generation_run_id=next_generation_run_id,
            )
        )
        retire_preview_ids = preview_ids_for_run_transition(
            source_preview_ids_by_key=source_preview_ids_by_key,
            source_preview_ids_by_slot=source_preview_ids_by_slot,
            scene_preview_ids_by_slot=scene_preview_ids_by_slot,
            scene_preview_slots_by_key=scene_preview_slots_by_key,
        )
    return PreviewRunTransitionPlan(
        retire_preview_ids=retire_preview_ids,
        retire_scene_run_id=active_run_id,
        retained_completed_slots=retained_completed_slots,
        next_generation_run_id=next_generation_run_id,
        next_scene_run_id=next_scene_run_id,
    )


def apply_preview_run_transition(
    cache: OutputCanvasRevisionCache,
    transition: PreviewRunTransitionPlan,
    *,
    completed_preview_slots: set[PreviewSlotKey],
) -> None:
    """Persist application-owned state after a preview run transition."""

    completed_preview_slots.intersection_update(transition.retained_completed_slots)
    cache.active_preview_generation_run_id = transition.next_generation_run_id
    cache.active_preview_scene_run_id = transition.next_scene_run_id


def scene_group_without_preview(
    scene: OutputCanvasSceneGroup,
) -> OutputCanvasSceneGroup:
    """Return a scene group with preview imagery removed and final state preserved."""

    return OutputCanvasSceneGroup(
        scene_run_id=scene.scene_run_id,
        scene_key=scene.scene_key,
        title=scene.title,
        order=scene.order,
        sources=scene.sources,
        preview_image_id=None,
        primary_image_id=scene.primary_image_id,
        representative_source_key=scene.representative_source_key,
        representative_set_index=scene.representative_set_index,
        status=scene.status,
        title_is_default=scene.title_is_default,
    )


def preview_retirement_plan(
    *,
    preview_id: UUID,
    source_preview_ids_by_key: Mapping[str, UUID],
    source_preview_ids_by_slot: Mapping[SourcePreviewSlotKey, UUID],
    scene_preview_ids_by_slot: Mapping[PreviewSlotKey, UUID],
    scene_preview_slots_by_key: Mapping[str, ScenePreviewSlot],
    preview_scene_groups_by_key: Mapping[str, OutputCanvasSceneGroup],
    base_scene_groups_by_key: Mapping[str, OutputCanvasSceneGroup],
) -> PreviewRetirementPlan:
    """Return cache mutations required to remove one retired preview image."""

    removed_source_keys = tuple(
        key for key, value in source_preview_ids_by_key.items() if value == preview_id
    )
    removed_source_slots = tuple(
        key for key, value in source_preview_ids_by_slot.items() if value == preview_id
    )
    removed_scene_slots = tuple(
        key for key, value in scene_preview_ids_by_slot.items() if value == preview_id
    )
    removed_accepted_scene_keys = tuple(
        key
        for key, slot in scene_preview_slots_by_key.items()
        if slot.preview_id == preview_id
    )

    removed_preview_scene_group_keys: list[str] = []
    updated_preview_scene_groups: dict[str, OutputCanvasSceneGroup] = {}
    for key, scene in preview_scene_groups_by_key.items():
        if scene.preview_image_id != preview_id:
            continue
        if scene.primary_image_id is None:
            removed_preview_scene_group_keys.append(key)
            continue
        updated_preview_scene_groups[key] = scene_group_without_preview(scene)

    remaining_preview_scene_keys = set(preview_scene_groups_by_key) - set(
        removed_preview_scene_group_keys
    )
    for key, scene in base_scene_groups_by_key.items():
        if key in remaining_preview_scene_keys or scene.preview_image_id != preview_id:
            continue
        updated_preview_scene_groups[key] = scene_group_without_preview(scene)

    return PreviewRetirementPlan(
        removed_source_keys=removed_source_keys,
        removed_source_slots=removed_source_slots,
        removed_scene_slots=removed_scene_slots,
        removed_accepted_scene_keys=removed_accepted_scene_keys,
        removed_preview_scene_group_keys=tuple(removed_preview_scene_group_keys),
        updated_preview_scene_groups=tuple(updated_preview_scene_groups.items()),
    )


def final_output_preview_retirement(
    *,
    image_id: UUID,
    pending_final_preview_retire_ids: Container[UUID],
    source_key: str,
    image_meta: ImageMeta,
    set_index: int,
) -> FinalOutputPreviewRetirement | None:
    """Return the preview-retirement command for a selected final output."""

    if image_id not in pending_final_preview_retire_ids:
        return None
    return FinalOutputPreviewRetirement(
        slot_key=PreviewSlotKey(
            scene_run_id=image_meta.scene_run_id,
            generation_run_id=image_meta.generation_run_id,
            scene_key=image_meta.scene_key,
            source_key=source_key,
            set_index=set_index,
        ),
        source_label=image_meta.source_label,
    )


def consume_final_output_preview_retirement(
    *,
    image_id: UUID,
    pending_final_preview_retire_ids: set[UUID],
    source_key: str,
    image_meta: ImageMeta,
    set_index: int,
) -> FinalOutputPreviewRetirement | None:
    """Return and consume the pending retirement command for a final output."""

    retirement = final_output_preview_retirement(
        image_id=image_id,
        pending_final_preview_retire_ids=pending_final_preview_retire_ids,
        source_key=source_key,
        image_meta=image_meta,
        set_index=set_index,
    )
    if retirement is None:
        return None
    pending_final_preview_retire_ids.remove(image_id)
    return retirement


def apply_preview_retirement_plan(
    retirement: PreviewRetirementPlan,
    *,
    source_preview_ids_by_key: MutableMapping[str, UUID],
    preview_labels_by_source_key: MutableMapping[str, str],
    preview_images_by_source_key: MutableMapping[str, object],
    source_preview_ids_by_slot: MutableMapping[SourcePreviewSlotKey, UUID],
    scene_preview_ids_by_slot: MutableMapping[PreviewSlotKey, UUID],
    scene_preview_slots_by_key: MutableMapping[str, ScenePreviewSlot],
    preview_scene_groups_by_key: MutableMapping[str, OutputCanvasSceneGroup],
) -> None:
    """Apply preview retirement mutations to application-owned preview maps."""

    for source_key in retirement.removed_source_keys:
        source_preview_ids_by_key.pop(source_key, None)
        preview_labels_by_source_key.pop(source_key, None)
        preview_images_by_source_key.pop(source_key, None)
    for source_slot in retirement.removed_source_slots:
        source_preview_ids_by_slot.pop(source_slot, None)
    for scene_slot in retirement.removed_scene_slots:
        scene_preview_ids_by_slot.pop(scene_slot, None)
    for scene_key in retirement.removed_accepted_scene_keys:
        scene_preview_slots_by_key.pop(scene_key, None)
    for scene_key in retirement.removed_preview_scene_group_keys:
        preview_scene_groups_by_key.pop(scene_key, None)
    for scene_key, scene in retirement.updated_preview_scene_groups:
        preview_scene_groups_by_key[scene_key] = scene


def preview_registry_snapshot(
    *,
    source_preview_ids_by_key: Mapping[str, UUID],
    source_preview_ids_by_slot: Mapping[SourcePreviewSlotKey, UUID],
    scene_preview_ids_by_slot: Mapping[PreviewSlotKey, UUID],
    scene_preview_slots_by_key: Mapping[str, ScenePreviewSlot],
    preview_images_by_id: Mapping[UUID, object],
    completed_preview_slots: Iterable[PreviewSlotKey],
    unscoped_preview_id: UUID | None = None,
) -> dict[str, object]:
    """Return compact preview registry diagnostics for lifecycle logging."""

    known_preview_ids = set(source_preview_ids_by_key.values())
    known_preview_ids.update(source_preview_ids_by_slot.values())
    known_preview_ids.update(scene_preview_ids_by_slot.values())
    known_preview_ids.update(
        slot.preview_id for slot in scene_preview_slots_by_key.values()
    )
    if unscoped_preview_id is not None:
        known_preview_ids.add(unscoped_preview_id)
    cached_preview_ids = tuple(
        str(preview_id)
        for preview_id in known_preview_ids
        if preview_id in preview_images_by_id
    )
    missing_preview_ids = tuple(
        str(preview_id)
        for preview_id in known_preview_ids
        if preview_id not in preview_images_by_id
    )
    return {
        "preview_registry_source_ids": tuple(
            (source_key, str(preview_id))
            for source_key, preview_id in source_preview_ids_by_key.items()
        ),
        "preview_registry_source_fingerprints": tuple(
            (
                source_key,
                None,
            )
            for source_key, preview_id in source_preview_ids_by_key.items()
        ),
        "preview_registry_source_slot_ids": tuple(
            (
                slot.scene_run_id,
                slot.scene_key,
                slot.source_key,
                slot.set_index,
                str(preview_id),
            )
            for slot, preview_id in source_preview_ids_by_slot.items()
        ),
        "preview_registry_scene_slot_ids": tuple(
            (
                slot.scene_run_id,
                slot.scene_key,
                slot.source_key,
                slot.set_index,
                str(preview_id),
            )
            for slot, preview_id in scene_preview_ids_by_slot.items()
        ),
        "preview_registry_accepted_scene_slots": tuple(
            (
                scene_key,
                slot.scene_run_id,
                slot.source_key,
                slot.source_label,
                slot.set_index,
                str(slot.preview_id),
                None,
            )
            for scene_key, slot in scene_preview_slots_by_key.items()
        ),
        "preview_registry_cached_ids": cached_preview_ids,
        "preview_registry_missing_ids": missing_preview_ids,
        "preview_registry_completed_slots": tuple(
            (
                slot.scene_run_id,
                slot.scene_key,
                slot.source_key,
                slot.set_index,
            )
            for slot in completed_preview_slots
        ),
        "preview_registry_total_cached_images": len(preview_images_by_id),
    }


def source_is_new_for_scene(
    scene: OutputCanvasSceneGroup,
    source_key: str,
) -> bool:
    """Return whether a preview source has no completed scene outputs yet."""

    return all(source.source_key != source_key for source in scene.sources)


def source_is_after(
    scene: OutputCanvasSceneGroup,
    source_key: str,
    baseline_source_key: str | None,
) -> bool:
    """Return whether a source appears after another completed scene source."""

    if baseline_source_key is None:
        return False
    source_keys = tuple(source.source_key for source in scene.sources)
    try:
        preview_index = source_keys.index(source_key)
        baseline_index = source_keys.index(baseline_source_key)
    except ValueError:
        return False
    return preview_index > baseline_index


def scene_preview_id_for_source(
    preview_ids_by_scene_slot: MutableMapping[PreviewSlotKey, UUID],
    *,
    generation_run_id: str,
    scene_run_id: str,
    scene_key: str,
    source_key: str,
    set_index: int = 1,
) -> UUID:
    """Return stable preview id for one scene/source representative slot."""

    return preview_ids_by_scene_slot.setdefault(
        PreviewSlotKey(
            scene_run_id=scene_run_id,
            generation_run_id=generation_run_id,
            scene_key=scene_key,
            source_key=source_key,
            set_index=set_index,
        ),
        uuid4(),
    )


__all__ = [
    "CompletedSlotPreviewRetirementPlan",
    "FinalOutputPreviewRetirement",
    "OutputCanvasRevisionCacheBinding",
    "OutputCanvasRevisionCache",
    "PreviewSlotKey",
    "PreviewRetirementPlan",
    "PreviewRunTransitionPlan",
    "ScenePreviewSlot",
    "SourcePreviewSlotKey",
    "apply_preview_retirement_plan",
    "apply_preview_run_transition",
    "completed_slot_preview_retirement_plan",
    "completed_preview_slots_for_generation",
    "consume_final_output_preview_retirement",
    "final_output_preview_retirement",
    "output_revision_cache_binding",
    "preview_slot_matches_completed_output",
    "preview_slot_for_scene",
    "preview_slot_is_completed",
    "preview_ids_for_completed_slot",
    "preview_ids_for_run_transition",
    "preview_registry_snapshot",
    "preview_retirement_plan",
    "preview_run_transition_plan",
    "scene_group_without_preview",
    "scene_has_completed_source_label_set",
    "scene_has_completed_source_set",
    "scene_preview_id_for_source",
    "scene_preview_matches_representative",
    "source_is_after",
    "source_is_new_for_scene",
    "source_label_for_key",
    "source_labels_match",
]

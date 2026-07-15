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

"""Execute Output canvas preview-retirement host side effects."""

from __future__ import annotations

from uuid import UUID

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
)
from substitute.application.workflows.output_preview_lifecycle_service import (
    PreviewSlotKey,
    apply_preview_retirement_plan,
    completed_slot_preview_retirement_plan,
    preview_retirement_plan,
)
from substitute.presentation.canvas.output.output_canvas_preview_state import (
    output_preview_registry,
    output_revision_cache,
)
from substitute.presentation.canvas.output.output_canvas_route_state import (
    output_route_state_snapshot,
    output_scene_groups_by_key,
)
from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger("presentation.canvas.output.output_canvas_preview_retirement")


def retire_output_preview_id(
    host: object,
    preview_id: UUID,
    *,
    retire_reason: str,
    scene_run_id: str = "",
    scene_key: str = "",
    source_key: str = "",
    set_index: int | None = None,
) -> None:
    """Remove one transient preview image from an Output host."""

    runtime = getattr(host, "_runtime", None)
    core = getattr(runtime, "core", None)
    asset_lookup = getattr(core, "asset_lookup", None) or getattr(host, "_asset_lookup")
    asset_lookup.preview_images().pop(preview_id, None)
    cache = output_revision_cache(host)
    preview_scene_groups = cache.preview_scene_groups_by_key
    projection = getattr(host, "_output_projection", None)
    base_scene_groups = (
        {scene.scene_key: scene for scene in projection.scene_groups}
        if isinstance(projection, OutputCanvasProjection)
        else {}
    )
    retirement = preview_retirement_plan(
        preview_id=preview_id,
        source_preview_ids_by_key=cache.preview_ids_by_source_key,
        source_preview_ids_by_slot=cache.preview_ids_by_source_slot,
        scene_preview_ids_by_slot=cache.preview_ids_by_scene_slot,
        scene_preview_slots_by_key=cache.scene_preview_slots_by_key,
        preview_scene_groups_by_key=preview_scene_groups,
        base_scene_groups_by_key=base_scene_groups,
    )
    apply_preview_retirement_plan(
        retirement,
        source_preview_ids_by_key=cache.preview_ids_by_source_key,
        preview_labels_by_source_key=cache.preview_labels_by_source_key,
        preview_images_by_source_key=cache.preview_images_by_source_key,
        source_preview_ids_by_slot=cache.preview_ids_by_source_slot,
        scene_preview_ids_by_slot=cache.preview_ids_by_scene_slot,
        scene_preview_slots_by_key=cache.scene_preview_slots_by_key,
        preview_scene_groups_by_key=preview_scene_groups,
    )

    output_preview_registry(host).retire_preview_id(preview_id)
    qpane_presenter = getattr(core, "qpane_presenter", None) or getattr(
        host, "_qpane_presenter"
    )
    qpane_presenter.remove_image(preview_id)
    log_debug(
        _LOGGER,
        "Retired output preview image.",
        preview_id=preview_id,
        retire_reason=retire_reason,
        workflow_id=getattr(host, "_projection_workflow_id", ""),
        generation_run_id=cache.active_preview_generation_run_id,
        scene_run_id=scene_run_id,
        scene_key=scene_key,
        source_key=source_key,
        set_index="" if set_index is None else set_index,
        removed_source_key_count=len(retirement.removed_source_keys),
        removed_source_slot_count=len(retirement.removed_source_slots),
        removed_scene_slot_count=len(retirement.removed_scene_slots),
        removed_accepted_scene_count=len(retirement.removed_accepted_scene_keys),
        removed_preview_scene_group_count=len(
            retirement.removed_preview_scene_group_keys
        ),
        updated_preview_scene_group_count=len(retirement.updated_preview_scene_groups),
    )


def retire_output_previews_for_completed_slot(
    host: object,
    slot_key: PreviewSlotKey,
    *,
    source_label: str = "",
    retire_reason: str,
) -> None:
    """Retire every preview image associated with one completed final slot."""

    cache = output_revision_cache(host)
    accepted_slot = cache.scene_preview_slots_by_key.get(slot_key.scene_key)
    scene = output_scene_groups_by_key(output_route_state_snapshot(host)).get(
        slot_key.scene_key
    )
    retirement = completed_slot_preview_retirement_plan(
        slot_key=slot_key,
        source_label=source_label,
        accepted_slot=accepted_slot,
        scene=scene,
        scene_preview_ids_by_slot=cache.preview_ids_by_scene_slot,
        source_preview_ids_by_slot=cache.preview_ids_by_source_slot,
        source_preview_ids_by_key=cache.preview_ids_by_source_key,
    )
    for preview_id in retirement.retire_preview_ids:
        retire_output_preview_id(
            host,
            preview_id,
            retire_reason=retire_reason,
            scene_run_id=retirement.scene_run_id,
            scene_key=retirement.scene_key,
            source_key=retirement.source_key,
            set_index=retirement.set_index,
        )


__all__ = [
    "retire_output_preview_id",
    "retire_output_previews_for_completed_slot",
]

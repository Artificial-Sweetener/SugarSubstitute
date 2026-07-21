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

"""Partition reorder paint between projection-surface and overlay owners."""

from __future__ import annotations

from dataclasses import dataclass, replace

from PySide6.QtGui import QColor

from ..projection.reorder_surface_chrome import (
    PromptReorderSurfaceChromeChip,
    PromptReorderSurfaceChromeStyle,
)
from ..projection.reorder_animation import (
    PromptReorderAnimationFallback,
    PromptReorderAnimationPlan,
)
from .reorder_view import PromptReorderChipPaintState, PromptReorderViewRenderState


@dataclass(frozen=True, slots=True)
class PromptReorderPaintOwnership:
    """Carry stationary surface chrome and transient overlay paint separately."""

    surface_chips: tuple[PromptReorderSurfaceChromeChip, ...]
    overlay_state: PromptReorderViewRenderState
    unsafe_transient_indices: tuple[int, ...]


def partition_reorder_paint_ownership(
    state: PromptReorderViewRenderState,
) -> PromptReorderPaintOwnership:
    """Assign stationary chrome below text and moving complete chips above it."""

    active_chips = state.preview_chips if state.preview_active else state.live_chips
    surface_chips = tuple(
        _surface_chrome_chip(chip)
        for chip in active_chips
        if chip.geometry is not None and not chip.owns_projection_text
    )
    overlay_chips = tuple(chip for chip in active_chips if chip.owns_projection_text)
    unsafe_indices = tuple(
        chip.segment_index
        for chip in active_chips
        if chip.geometry is None and not chip.owns_projection_text
    )
    overlay_state = replace(
        state,
        live_chips=overlay_chips if not state.preview_active else (),
        preview_chips=overlay_chips if state.preview_active else (),
        raster_paint_count=sum(1 for chip in overlay_chips if chip.raster_entry),
    )
    return PromptReorderPaintOwnership(
        surface_chips=surface_chips,
        overlay_state=overlay_state,
        unsafe_transient_indices=unsafe_indices,
    )


def animation_plan_with_complete_paint_ownership(
    plan: PromptReorderAnimationPlan,
    *,
    snapshot_indices: frozenset[int],
) -> PromptReorderAnimationPlan:
    """Animate only chips whose translated chrome also owns complete text paint."""

    animated_targets = tuple(
        target
        for target in plan.changed_targets
        if target.segment_index in snapshot_indices
    )
    immediate_fallbacks = tuple(
        target
        for target in plan.changed_targets
        if target.segment_index not in snapshot_indices
    )
    if not immediate_fallbacks:
        return plan
    fallback_indices = frozenset(target.segment_index for target in immediate_fallbacks)
    return replace(
        plan,
        changed_targets=animated_targets,
        immediate_targets=plan.immediate_targets + immediate_fallbacks,
        immediate_segment_indices=plan.immediate_segment_indices | fallback_indices,
        fallbacks=plan.fallbacks
        + tuple(
            PromptReorderAnimationFallback(
                segment_index=target.segment_index,
                disposition="immediate",
                reason="projection_paint_snapshot_missing",
                generation=plan.generation,
                has_current_rect=True,
                has_target_rect=True,
                target_visible=target.target_visible,
            )
            for target in immediate_fallbacks
        ),
    )


def _surface_chrome_chip(
    chip: PromptReorderChipPaintState,
) -> PromptReorderSurfaceChromeChip:
    """Convert one stationary overlay plan item into surface-owned chrome."""

    geometry = chip.geometry
    if geometry is None:
        raise ValueError("Surface chrome requires projection-owned chip geometry.")
    style = chip.style
    return PromptReorderSurfaceChromeChip(
        segment_index=chip.segment_index,
        geometry=geometry,
        style=PromptReorderSurfaceChromeStyle(
            fill_color=QColor(style.fill_color),
            border_color=QColor(style.border_color),
            outline_only=style.outline_only,
            outline_width=style.outline_width,
            opacity=style.opacity,
        ),
    )


__all__ = [
    "PromptReorderPaintOwnership",
    "animation_plan_with_complete_paint_ownership",
    "partition_reorder_paint_ownership",
]

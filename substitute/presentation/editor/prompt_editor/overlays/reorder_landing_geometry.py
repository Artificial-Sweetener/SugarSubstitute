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

"""Derive reorder landing visuals, geometry, and target-match policy."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRect, QRectF

from ..projection.reorder_chip_geometry import (
    PromptReorderChipGeometry,
    PromptReorderChipGeometryId,
    PromptReorderChipLineGeometry,
    chrome_path_from_rects,
)
from .chip_visuals import PromptChipVisual, prompt_chip_bubble_union_rect
from .reorder_landing_models import (
    PromptReorderHeldShadowGeometry,
    PromptReorderLandingShadowRequest,
)

_INITIAL_LANDING_SHADOW_MIN_WIDTH = 24.0
_TARGET_LANDING_MISMATCH_X = 24.0


@dataclass(frozen=True, slots=True)
class PromptReorderLandingTargetMatch:
    """Describe target acceptance and any anchor mismatch diagnostics."""

    accepted: bool
    rejection_reason: str | None = None
    anchor_dx: float | None = None
    anchor_dy: float | None = None
    threshold_x: float | None = None
    threshold_y: float | None = None


def prompt_reorder_placement_landing_geometry(
    request: PromptReorderLandingShadowRequest,
    held: PromptReorderHeldShadowGeometry | None,
) -> PromptReorderChipGeometry | None:
    """Build current-target landing geometry from placement and held chrome."""

    if (
        request.dragged_segment_index is None
        or request.active_target is None
        or request.active_placement is None
        or held is None
        or held.chip_index != request.dragged_segment_index
        or request.dragged_segment is None
    ):
        return None
    anchor_rect = request.active_placement.insertion_anchor_rect
    top_left = QPointF(
        anchor_rect.center().x(),
        anchor_rect.center().y() - (held.chrome_bounds.height() / 2.0),
    )
    visual = prompt_reorder_clamp_shadow_visual(
        prompt_reorder_translated_held_shadow_visual(held, top_left),
        content_rect=request.content_rect,
        overlay_rect=request.overlay_rect,
    )
    content_rects = visual.bubble_rects
    if not content_rects:
        return None
    visual_lines = tuple(
        PromptReorderChipLineGeometry(
            visual_line_index=(
                request.active_placement.placement_id.visual_line_index + line_offset
            ),
            line_rect=QRectF(request.active_placement.visual_line_rect),
            content_rect=QRectF(content_rect),
            leading_anchor=QPointF(content_rect.left(), content_rect.center().y()),
            trailing_anchor=QPointF(content_rect.right(), content_rect.center().y()),
        )
        for line_offset, content_rect in enumerate(content_rects)
    )
    return PromptReorderChipGeometry(
        geometry_id=PromptReorderChipGeometryId(
            chip_index=request.dragged_segment_index,
            visual_revision=-(request.event_id or 0),
        ),
        chip_index=request.dragged_segment_index,
        source_start=request.dragged_segment.selection_start,
        source_end=request.dragged_segment.selection_end,
        rendered_start=request.dragged_segment.selection_start,
        rendered_end=request.dragged_segment.selection_end,
        visual_lines=visual_lines,
        hotspot_rect=QRect(visual.hotspot_rect),
        chrome_path=chrome_path_from_rects(
            tuple(QRectF(rect) for rect in content_rects)
        ),
        outline_bounds=prompt_chip_bubble_union_rect(content_rects),
        slot_before=QPointF(visual.slot_before),
        slot_after=QPointF(visual.slot_after),
        marker_height=visual.marker_height,
    )


def prompt_reorder_pending_shadow_visual(
    request: PromptReorderLandingShadowRequest,
    held: PromptReorderHeldShadowGeometry | None,
) -> PromptChipVisual | None:
    """Build provisional landing chrome from the held geometry and placement."""

    if (
        request.dragged_segment_index is None
        or request.active_target is None
        or request.active_placement is None
        or held is None
        or held.chip_index != request.dragged_segment_index
    ):
        return None
    anchor_rect = request.active_placement.insertion_anchor_rect
    top_left = QPointF(
        anchor_rect.center().x(),
        anchor_rect.center().y() - (held.chrome_bounds.height() / 2.0),
    )
    return prompt_reorder_clamp_shadow_visual(
        prompt_reorder_translated_held_shadow_visual(held, top_left),
        content_rect=request.content_rect,
        overlay_rect=request.overlay_rect,
    )


def prompt_reorder_translated_held_shadow_visual(
    held: PromptReorderHeldShadowGeometry,
    top_left: QPointF,
) -> PromptChipVisual:
    """Translate normalized held chrome into overlay coordinates."""

    bubble_rects = tuple(
        QRectF(rect).translated(top_left) for rect in held.normalized_bubble_rects
    )
    chrome_bounds = prompt_chip_bubble_union_rect(bubble_rects)
    hotspot_rect = QRectF(held.hotspot_bounds).translated(top_left)
    first_rect = bubble_rects[0]
    last_rect = bubble_rects[-1]
    return PromptChipVisual(
        bubble_rects=bubble_rects,
        fragment_union_rect=chrome_bounds,
        hotspot_rect=hotspot_rect.toAlignedRect(),
        slot_before=QPointF(first_rect.left(), first_rect.center().y()),
        slot_after=QPointF(last_rect.right(), last_rect.center().y()),
        marker_height=max(rect.height() for rect in bubble_rects),
    )


def prompt_reorder_clamp_shadow_visual(
    visual: PromptChipVisual,
    *,
    content_rect: QRectF,
    overlay_rect: QRectF,
) -> PromptChipVisual:
    """Keep provisional chrome visible by translating without resizing."""

    chrome_bounds = prompt_chip_bubble_union_rect(visual.bubble_rects)
    clamped_bounds = prompt_reorder_clamp_shadow_rect(
        chrome_bounds,
        content_rect=content_rect,
        overlay_rect=overlay_rect,
    )
    delta = clamped_bounds.topLeft() - chrome_bounds.topLeft()
    if delta.isNull():
        return visual
    translated_bubbles = tuple(
        QRectF(rect).translated(delta) for rect in visual.bubble_rects
    )
    translated_hotspot = QRectF(visual.hotspot_rect).translated(delta)
    translated_union = QRectF(visual.fragment_union_rect).translated(delta)
    return PromptChipVisual(
        bubble_rects=translated_bubbles,
        fragment_union_rect=translated_union,
        hotspot_rect=translated_hotspot.toAlignedRect(),
        slot_before=visual.slot_before + delta,
        slot_after=visual.slot_after + delta,
        marker_height=visual.marker_height,
    )


def prompt_reorder_clamp_shadow_rect(
    rect: QRectF,
    *,
    content_rect: QRectF,
    overlay_rect: QRectF,
) -> QRectF:
    """Keep provisional bounds visible without changing their cached size."""

    bounds = QRectF(content_rect)
    if not bounds.isValid() or bounds.isEmpty():
        bounds = QRectF(overlay_rect)
    if not bounds.isValid() or bounds.isEmpty():
        return rect
    left = rect.left()
    if rect.width() <= bounds.width():
        left = min(max(left, bounds.left()), bounds.right() - rect.width())
    top = rect.top()
    if rect.height() <= bounds.height():
        top = min(max(top, bounds.top()), bounds.bottom() - rect.height())
    return QRectF(left, top, rect.width(), rect.height())


def prompt_reorder_is_chip_shaped_landing(
    request: PromptReorderLandingShadowRequest,
    geometry: PromptReorderChipGeometry | None,
) -> bool:
    """Return whether geometry is a real chip shadow rather than an anchor."""

    if geometry is None or request.dragged_segment_index is None:
        return False
    return (
        geometry.chip_index == request.dragged_segment_index
        and not geometry.chrome_path.isEmpty()
        and geometry.outline_bounds.width() >= _INITIAL_LANDING_SHADOW_MIN_WIDTH
        and geometry.hotspot_rect.width() >= _INITIAL_LANDING_SHADOW_MIN_WIDTH
    )


def prompt_reorder_landing_target_match(
    request: PromptReorderLandingShadowRequest,
    geometry: PromptReorderChipGeometry,
) -> PromptReorderLandingTargetMatch:
    """Classify whether one landing shadow agrees with the active target."""

    if request.dragged_segment_index is None:
        return PromptReorderLandingTargetMatch(False)
    if geometry.chip_index != request.dragged_segment_index:
        return PromptReorderLandingTargetMatch(False, "wrong_chip")
    if request.active_target is None or request.active_placement is None:
        return PromptReorderLandingTargetMatch(False)
    if request.active_placement.target != request.active_target:
        return PromptReorderLandingTargetMatch(False, "placement_target_mismatch")
    if (
        request.active_placement.expected_landing_chip_index is not None
        and request.active_placement.expected_landing_chip_index
        != request.dragged_segment_index
    ):
        return PromptReorderLandingTargetMatch(False, "expected_chip_mismatch")
    if (
        request.preview_geometry_target_identity is not None
        and request.expected_preview_target_identity is not None
        and request.preview_geometry_target_identity
        != request.expected_preview_target_identity
    ):
        return PromptReorderLandingTargetMatch(False, "preview_target_mismatch")
    anchor_rect = request.active_placement.insertion_anchor_rect
    landing_anchor = geometry.slot_before
    anchor_dx = abs(landing_anchor.x() - anchor_rect.center().x())
    anchor_dy = abs(landing_anchor.y() - anchor_rect.center().y())
    return PromptReorderLandingTargetMatch(
        accepted=True,
        anchor_dx=anchor_dx,
        anchor_dy=anchor_dy,
        threshold_x=_TARGET_LANDING_MISMATCH_X,
        threshold_y=max(1.0, anchor_rect.height()),
    )


__all__ = [
    "PromptReorderLandingTargetMatch",
    "prompt_reorder_clamp_shadow_rect",
    "prompt_reorder_clamp_shadow_visual",
    "prompt_reorder_is_chip_shaped_landing",
    "prompt_reorder_landing_target_match",
    "prompt_reorder_pending_shadow_visual",
    "prompt_reorder_placement_landing_geometry",
    "prompt_reorder_translated_held_shadow_visual",
]

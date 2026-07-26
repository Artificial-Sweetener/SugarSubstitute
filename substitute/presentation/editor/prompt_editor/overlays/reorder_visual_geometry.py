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

"""Adapt projection-owned chip geometry into immutable overlay visuals."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF

from ..projection.reorder_chip_geometry import PromptReorderChipGeometry
from .chip_visuals import PromptChipVisual


def prompt_reorder_visual_for_chip_geometry(
    geometry: PromptReorderChipGeometry,
) -> PromptChipVisual:
    """Return overlay chrome geometry for one projection-owned chip."""

    return PromptChipVisual(
        bubble_rects=tuple(line.content_rect for line in geometry.visual_lines),
        fragment_union_rect=QRectF(geometry.outline_bounds),
        hotspot_rect=geometry.hotspot_rect,
        slot_before=geometry.slot_before,
        slot_after=geometry.slot_after,
        marker_height=geometry.marker_height,
    )


def reorder_visual_translated_to_hotspot_rect(
    visual: PromptChipVisual | None,
    hotspot_rect: QRectF,
) -> PromptChipVisual | None:
    """Translate one visual so its hotspot starts at the target rectangle."""

    if visual is None:
        return None
    current_hotspot = QRectF(visual.hotspot_rect)
    dx = hotspot_rect.left() - current_hotspot.left()
    dy = hotspot_rect.top() - current_hotspot.top()
    return PromptChipVisual(
        bubble_rects=tuple(rect.translated(dx, dy) for rect in visual.bubble_rects),
        fragment_union_rect=visual.fragment_union_rect.translated(dx, dy),
        hotspot_rect=QRectF(hotspot_rect).toAlignedRect(),
        slot_before=visual.slot_before + QPointF(dx, dy),
        slot_after=visual.slot_after + QPointF(dx, dy),
        marker_height=visual.marker_height,
        preferred_size=visual.preferred_size,
        text_translation=visual.text_translation,
    )


__all__ = [
    "prompt_reorder_visual_for_chip_geometry",
    "reorder_visual_translated_to_hotspot_rect",
]

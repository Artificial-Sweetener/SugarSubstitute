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

"""Derive normalized held-chip chrome for reorder landing feedback."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, QSizeF

from .chip_visuals import prompt_chip_bubble_union_rect
from .reorder_landing_models import (
    PromptReorderHeldShadowCaptureInput,
    PromptReorderHeldShadowGeometry,
)


@dataclass(frozen=True, slots=True)
class PromptReorderHeldShadowCaptureOutcome:
    """Return normalized geometry plus bounded failure diagnostics."""

    geometry: PromptReorderHeldShadowGeometry | None
    source: str
    bubble_count: int
    chrome_bounds: QRectF
    hotspot_bounds: QRectF


def prompt_reorder_held_shadow_capture(
    capture: PromptReorderHeldShadowCaptureInput,
) -> PromptReorderHeldShadowCaptureOutcome:
    """Select the strongest available held-chip source and normalize its chrome."""

    if capture.live_geometry is not None:
        return _normalized_capture(
            chip_index=capture.chip_index,
            bubble_rects=tuple(
                line.content_rect for line in capture.live_geometry.visual_lines
            ),
            hotspot_bounds=QRectF(capture.live_geometry.hotspot_rect),
            source="live_chip_geometry",
        )
    if capture.base_drag_geometry is not None:
        return _normalized_capture(
            chip_index=capture.chip_index,
            bubble_rects=tuple(
                line.content_rect for line in capture.base_drag_geometry.visual_lines
            ),
            hotspot_bounds=QRectF(capture.base_drag_geometry.hotspot_rect),
            source="base_drag_chip_geometry",
        )
    if capture.live_visual is not None:
        return _normalized_capture(
            chip_index=capture.chip_index,
            bubble_rects=capture.live_visual.bubble_rects,
            hotspot_bounds=QRectF(capture.live_visual.hotspot_rect),
            source="live_chip_visual",
        )
    if not capture.chip_size.isEmpty():
        chip_rect = QRectF(QPointF(0.0, 0.0), QSizeF(capture.chip_size))
        return _normalized_capture(
            chip_index=capture.chip_index,
            bubble_rects=(chip_rect,),
            hotspot_bounds=chip_rect,
            source="chip_widget",
            low_confidence=True,
        )
    proxy_size = capture.proxy_size
    if proxy_size.isEmpty():
        proxy_size = capture.proxy_size_hint
    if not proxy_size.isEmpty():
        proxy_rect = QRectF(QPointF(0.0, 0.0), QSizeF(proxy_size))
        return _normalized_capture(
            chip_index=capture.chip_index,
            bubble_rects=(proxy_rect,),
            hotspot_bounds=proxy_rect,
            source="drag_proxy",
            low_confidence=True,
        )
    return PromptReorderHeldShadowCaptureOutcome(
        geometry=None,
        source="missing",
        bubble_count=0,
        chrome_bounds=QRectF(),
        hotspot_bounds=QRectF(),
    )


def _normalized_capture(
    *,
    chip_index: int,
    bubble_rects: tuple[QRectF, ...],
    hotspot_bounds: QRectF,
    source: str,
    low_confidence: bool = False,
) -> PromptReorderHeldShadowCaptureOutcome:
    """Normalize valid held chrome to a placement-independent origin."""

    chrome_bounds = prompt_chip_bubble_union_rect(bubble_rects)
    if not bubble_rects or not chrome_bounds.isValid() or chrome_bounds.isEmpty():
        return PromptReorderHeldShadowCaptureOutcome(
            geometry=None,
            source=source,
            bubble_count=len(bubble_rects),
            chrome_bounds=chrome_bounds,
            hotspot_bounds=QRectF(hotspot_bounds),
        )
    normalized_bubble_rects = tuple(
        QRectF(rect).translated(-chrome_bounds.left(), -chrome_bounds.top())
        for rect in bubble_rects
    )
    normalized_hotspot_bounds = QRectF(hotspot_bounds).translated(
        -chrome_bounds.left(),
        -chrome_bounds.top(),
    )
    normalized_chrome_bounds = QRectF(chrome_bounds).translated(
        -chrome_bounds.left(),
        -chrome_bounds.top(),
    )
    return PromptReorderHeldShadowCaptureOutcome(
        geometry=PromptReorderHeldShadowGeometry(
            chip_index=chip_index,
            normalized_bubble_rects=normalized_bubble_rects,
            chrome_bounds=normalized_chrome_bounds,
            hotspot_bounds=normalized_hotspot_bounds,
            source=source,
            low_confidence=low_confidence,
        ),
        source=source,
        bubble_count=len(bubble_rects),
        chrome_bounds=chrome_bounds,
        hotspot_bounds=QRectF(hotspot_bounds),
    )


__all__ = [
    "PromptReorderHeldShadowCaptureOutcome",
    "prompt_reorder_held_shadow_capture",
]

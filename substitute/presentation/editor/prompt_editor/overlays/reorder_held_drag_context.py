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

"""Own held-drag intent geometry and retained landing-shadow capture."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from PySide6.QtCore import QPointF, QRectF, QSize, QSizeF

from ..projection.reorder_chip_geometry import PromptReorderChipGeometrySnapshot
from ..projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)
from .chip_visuals import PromptChipVisual
from .reorder_gesture_controller import PromptReorderGestureController
from .reorder_landing_models import PromptReorderHeldShadowCaptureInput
from .reorder_pointer_regions import PromptReorderPointerRegion


class PromptReorderHeldDragContextOwner:
    """Capture and clear one complete held-drag geometry context."""

    def __init__(
        self,
        *,
        gesture: PromptReorderGestureController,
        geometry_state: Callable[[], PromptReorderInteractionGeometryState],
        clear_geometry: Callable[[bool], None],
        live_visual_facts: Callable[
            [],
            tuple[
                Mapping[int, PromptChipVisual],
                PromptReorderChipGeometrySnapshot | None,
            ],
        ],
        regions_by_index: Callable[[], Mapping[int, PromptReorderPointerRegion]],
        proxy_sizes: Callable[[], tuple[QSize, QSize]],
        capture_held_shadow: Callable[[PromptReorderHeldShadowCaptureInput], None],
        clear_held_shadow: Callable[[], None],
        clear_landing_paint: Callable[[], None],
    ) -> None:
        """Store focused owners required only at drag start and teardown."""

        self._gesture = gesture
        self._geometry_state = geometry_state
        self._clear_geometry = clear_geometry
        self._live_visual_facts = live_visual_facts
        self._regions_by_index = regions_by_index
        self._proxy_sizes = proxy_sizes
        self._capture_held_shadow = capture_held_shadow
        self._clear_held_shadow = clear_held_shadow
        self._clear_landing_paint = clear_landing_paint

    def capture(
        self,
        segment_index: int,
        *,
        local_pointer: QPointF,
        gesture_id: int | None,
        event_id: int | None,
    ) -> None:
        """Capture logical grab geometry and the matching held shadow atomically."""

        self._gesture.capture_drag_intent_context(
            chip_rect=self._source_rect(segment_index),
            local_pointer=local_pointer,
        )
        base_geometry = None
        base_snapshot = self._geometry_state().base_drag_chip_geometry_snapshot
        if base_snapshot is not None:
            base_geometry = base_snapshot.geometries_by_chip_index.get(segment_index)
        visuals_by_index, live_snapshot = self._live_visual_facts()
        live_geometry = (
            None
            if live_snapshot is None
            else live_snapshot.geometries_by_chip_index.get(segment_index)
        )
        region = self._regions_by_index().get(segment_index)
        proxy_size, proxy_size_hint = self._proxy_sizes()
        self._capture_held_shadow(
            PromptReorderHeldShadowCaptureInput(
                chip_index=segment_index,
                live_geometry=live_geometry,
                base_drag_geometry=base_geometry,
                live_visual=visuals_by_index.get(segment_index),
                chip_size=QSize() if region is None else region.size(),
                proxy_size=proxy_size,
                proxy_size_hint=proxy_size_hint,
                gesture_id=gesture_id,
                event_id=event_id,
            )
        )

    def clear(self, *, preserve_preview: bool = False) -> None:
        """Clear every held and base-drag fact at the lifecycle boundary."""

        self._gesture.clear_drag_intent_context()
        self._gesture.clear_base_drag_segment()
        self._clear_geometry(preserve_preview)
        self._clear_held_shadow()
        self._clear_landing_paint()
        self._gesture.clear_keyboard_preferred_x()

    def _source_rect(self, segment_index: int) -> QRectF:
        """Return the best prepared source rect for logical held geometry."""

        region = self._regions_by_index().get(segment_index)
        if region is not None and not region.rect.isEmpty():
            return QRectF(region.rect)
        visual = self._live_visual_facts()[0].get(segment_index)
        if visual is not None and not visual.hotspot_rect.isEmpty():
            return QRectF(visual.hotspot_rect)
        return QRectF(QPointF(), QSizeF(1.0, 1.0))


__all__ = [
    "PromptReorderHeldDragContextOwner",
]

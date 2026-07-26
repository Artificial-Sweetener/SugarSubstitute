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

"""Own gesture-driven reorder preview-layout publication."""

from __future__ import annotations

from ..interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from ..projection.reorder_interaction_geometry import (
    PromptReorderInteractionGeometry,
)
from .reorder_drag_proxy_visual_owner import PromptReorderDragProxyVisualOwner
from .reorder_gesture_controller import PromptReorderGestureController
from .reorder_viewport_geometry import PromptReorderViewportGeometryOwner


class PromptReorderPreviewLayoutTransitionOwner:
    """Publish one preview layout from authoritative gesture and viewport facts."""

    def __init__(
        self,
        *,
        geometry: PromptReorderInteractionGeometry,
        gesture: PromptReorderGestureController,
        viewport: PromptReorderViewportGeometryOwner,
        drag_proxy: PromptReorderDragProxyVisualOwner,
        metrics: PromptReorderInteractionMetricsOwner,
    ) -> None:
        """Store focused publications used only by layout transitions."""

        self._geometry = geometry
        self._gesture = gesture
        self._viewport = viewport
        self._drag_proxy = drag_proxy
        self._metrics = metrics

    def update(self) -> bool:
        """Publish current gesture layout or stop before viewport work."""

        if self._geometry.state.document_view is None:
            return False
        gesture_state = self._gesture.state
        self._geometry.update_preview_layout(
            dragged_segment_index=gesture_state.dragged_segment_index,
            active_target=gesture_state.active_drop_target,
            viewport_identity=self._viewport.position_geometry_key(),
            gesture_id=self._metrics.gesture_id,
            event_id=self._metrics.event_id,
        )
        self._drag_proxy.raise_proxy()
        return True


__all__ = ["PromptReorderPreviewLayoutTransitionOwner"]

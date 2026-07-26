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

"""Build coherent landing requests from authoritative reorder publications."""

from __future__ import annotations

from PySide6.QtCore import QRectF

from ..interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from ..projection.reorder_interaction_geometry import (
    PromptReorderInteractionGeometry,
)
from ..projection.reorder_interaction_geometry_identity import (
    reorder_preview_target_identity,
)
from .reorder_gesture_controller import PromptReorderGestureController
from .reorder_landing_models import PromptReorderLandingShadowRequest
from .reorder_preview_visual_owner import PromptReorderPreviewVisualOwner
from .reorder_viewport_geometry import PromptReorderViewportGeometryOwner
from .reorder_visual_mode import PromptReorderVisualModeOwner
from .reorder_visual_session import PromptReorderVisualSessionOwner


class PromptReorderLandingRequestOwner:
    """Assemble one landing input from a single coherent owner-state read."""

    def __init__(
        self,
        *,
        geometry: PromptReorderInteractionGeometry,
        gesture: PromptReorderGestureController,
        metrics: PromptReorderInteractionMetricsOwner,
        preview_visuals: PromptReorderPreviewVisualOwner,
        viewport: PromptReorderViewportGeometryOwner,
        visual_mode: PromptReorderVisualModeOwner,
        visual_session: PromptReorderVisualSessionOwner,
    ) -> None:
        """Store the focused owners that publish landing input facts."""

        self._geometry = geometry
        self._gesture = gesture
        self._metrics = metrics
        self._preview_visuals = preview_visuals
        self._viewport = viewport
        self._visual_mode = visual_mode
        self._visual_session = visual_session

    def build(self) -> PromptReorderLandingShadowRequest:
        """Return one request without rescanning source or rebuilding geometry."""

        geometry_state = self._geometry.state
        gesture_state = self._gesture.state
        dragged_segment_index = gesture_state.dragged_segment_index
        active_target = gesture_state.active_drop_target
        viewport_identity = self._viewport.position_geometry_key()
        content_rect = QRectF(
            viewport_identity.content_left,
            viewport_identity.content_top,
            viewport_identity.content_width,
            viewport_identity.content_height,
        )
        overlay_rect = QRectF(
            viewport_identity.viewport_left,
            viewport_identity.viewport_top,
            viewport_identity.viewport_width,
            viewport_identity.viewport_height,
        )
        expected_identity = reorder_preview_target_identity(
            geometry_state,
            dragged_segment_index=dragged_segment_index,
            target=active_target,
            viewport_identity=viewport_identity,
        )
        preview_chip_snapshot = geometry_state.preview_chip_geometry_snapshot
        landing_geometry = (
            None
            if dragged_segment_index is None or preview_chip_snapshot is None
            else preview_chip_snapshot.geometries_by_chip_index.get(
                dragged_segment_index
            )
        )
        target_visual = next(
            (
                visual
                for visual in geometry_state.drop_target_visuals
                if visual.target == active_target
            ),
            None,
        )
        return PromptReorderLandingShadowRequest(
            gesture_id=self._metrics.gesture_id,
            event_id=self._metrics.event_id,
            dragged_segment_index=dragged_segment_index,
            active_target=active_target,
            active_placement=geometry_state.active_placement,
            dragged_segment=(
                None
                if dragged_segment_index is None
                else self._visual_session.segment(dragged_segment_index)
            ),
            content_rect=content_rect,
            overlay_rect=overlay_rect,
            preview_layout_active=self._visual_mode.preview_active(),
            preview_snapshot_available=geometry_state.preview_snapshot is not None,
            preview_visual_count=len(self._preview_visuals.visuals_by_index),
            landing_geometry=landing_geometry,
            target_visual=target_visual,
            preview_geometry_target_identity=(
                geometry_state.preview_geometry_target_identity
            ),
            expected_preview_target_identity=expected_identity,
            preview_target_identity_matches=(
                expected_identity is not None
                and geometry_state.preview_geometry_target_identity == expected_identity
            ),
        )


__all__ = ["PromptReorderLandingRequestOwner"]

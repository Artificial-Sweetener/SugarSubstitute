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

"""Own reorder insertion-marker visibility and prepared geometry."""

from __future__ import annotations

from PySide6.QtCore import QRectF

from ..interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from ..projection.observability import reorder_drag_rect_context
from ..projection.reorder_interaction_geometry import (
    PromptReorderInteractionGeometry,
)
from .reorder_gesture_controller import PromptReorderGestureController
from .reorder_interaction_diagnostics import (
    PromptReorderInteractionDiagnosticsOwner,
)
from .reorder_landing_models import PromptReorderLandingShadowRequest
from .reorder_landing_resolution import PromptReorderLandingResolutionOwner
from .reorder_telemetry import PromptReorderTelemetry

_INSERTION_WIDTH = 10.0


class PromptReorderInsertionMarkerOwner:
    """Prepare one marker from authoritative target and landing publications."""

    def __init__(
        self,
        *,
        geometry: PromptReorderInteractionGeometry,
        gesture: PromptReorderGestureController,
        landing_preview: PromptReorderLandingResolutionOwner,
        metrics: PromptReorderInteractionMetricsOwner,
        diagnostics: PromptReorderInteractionDiagnosticsOwner,
        telemetry: PromptReorderTelemetry,
    ) -> None:
        """Store focused marker inputs."""

        self._geometry = geometry
        self._gesture = gesture
        self._landing_preview = landing_preview
        self._metrics = metrics
        self._diagnostics = diagnostics
        self._telemetry = telemetry

    def marker_rect(
        self, *, landing_request: PromptReorderLandingShadowRequest | None
    ) -> QRectF | None:
        """Return the active insertion marker or the landing-owned suppression."""

        gesture_state = self._gesture.state
        dragged_segment_index = gesture_state.dragged_segment_index
        active_target = gesture_state.active_drop_target
        if dragged_segment_index is None or active_target is None:
            self._diagnostics.log_event(
                "target_visual.marker_skipped",
                gesture_id=self._metrics.gesture_id,
                event_id=self._metrics.event_id,
                has_dragged_segment=dragged_segment_index is not None,
                has_active_target=active_target is not None,
            )
            return None
        assert landing_request is not None, "Active marker requires landing state."
        if self._landing_preview.should_suppress_marker_for_landing_feedback(
            landing_request
        ):
            return None
        for visual in self._geometry.state.drop_target_visuals:
            if visual.target != active_target:
                continue
            marker_rect = QRectF(
                visual.hit_rect.center().x() - (_INSERTION_WIDTH / 2.0),
                visual.hit_rect.center().y() - (visual.hit_rect.height() / 2.0),
                _INSERTION_WIDTH,
                visual.hit_rect.height(),
            )
            self._diagnostics.log_event(
                "target_visual.marker_rect",
                gesture_id=self._metrics.gesture_id,
                event_id=self._metrics.event_id,
                **self._telemetry.target_context(active_target, prefix="active_target"),
                **reorder_drag_rect_context(visual.hit_rect, prefix="target_hit"),
                **reorder_drag_rect_context(marker_rect, prefix="marker"),
            )
            self._metrics.record_marker_fallback()
            return marker_rect
        self._diagnostics.log_anomaly(
            "anomaly.active_target_without_visual",
            dragged_segment_index=dragged_segment_index,
            **self._telemetry.target_context(active_target, prefix="active_target"),
        )
        return None

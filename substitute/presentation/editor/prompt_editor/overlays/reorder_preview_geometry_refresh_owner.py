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

"""Own one complete reorder preview-geometry publication transition."""

from __future__ import annotations

from ..interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from ..projection.observability import (
    reorder_drag_started_at,
    reorder_drag_target_kind,
)
from ..projection.reorder_interaction_geometry import (
    PromptReorderInteractionGeometry,
)
from .reorder_gesture_controller import PromptReorderGestureController
from .reorder_interaction_diagnostics import (
    PromptReorderInteractionDiagnosticsOwner,
)
from .reorder_landing_request_owner import PromptReorderLandingRequestOwner
from .reorder_landing_resolution import PromptReorderLandingResolutionOwner
from .reorder_preview_paint_snapshot_owner import (
    PromptReorderPreviewPaintSnapshotOwner,
)
from .reorder_preview_visual_owner import PromptReorderPreviewVisualOwner
from .reorder_viewport_geometry import PromptReorderViewportGeometryOwner

_SLOW_PREVIEW_GEOMETRY_MS = 8.0


class PromptReorderPreviewGeometryRefreshOwner:
    """Publish prepared preview geometry and its landing lifecycle atomically."""

    def __init__(
        self,
        *,
        geometry: PromptReorderInteractionGeometry,
        gesture: PromptReorderGestureController,
        viewport: PromptReorderViewportGeometryOwner,
        preview_visuals: PromptReorderPreviewVisualOwner,
        preview_paint_snapshots: PromptReorderPreviewPaintSnapshotOwner,
        landing_request: PromptReorderLandingRequestOwner,
        landing_preview: PromptReorderLandingResolutionOwner,
        metrics: PromptReorderInteractionMetricsOwner,
        diagnostics: PromptReorderInteractionDiagnosticsOwner,
    ) -> None:
        """Store the focused owners participating in one preview transition."""

        self._geometry = geometry
        self._gesture = gesture
        self._viewport = viewport
        self._preview_visuals = preview_visuals
        self._preview_paint_snapshots = preview_paint_snapshots
        self._landing_request = landing_request
        self._landing_preview = landing_preview
        self._metrics = metrics
        self._diagnostics = diagnostics

    def refresh(self) -> bool:
        """Refresh changed preview geometry and suppress all unchanged work."""

        started_at = reorder_drag_started_at()
        geometry_state = self._geometry.state
        preview_snapshot = geometry_state.preview_snapshot
        gesture_state = self._gesture.state
        outcome = self._preview_visuals.prepare(
            dragged_segment_index=gesture_state.dragged_segment_index,
            active_target=gesture_state.active_drop_target,
            viewport_identity=self._viewport.position_geometry_key(),
            gesture_id=self._metrics.gesture_id,
            event_id=self._metrics.event_id,
        )
        if not outcome.rebuilt:
            self._metrics.record_preview_geometry_suppressed()
            return False

        refresh = outcome.publication.geometry
        self._metrics.record_preview_geometry_build(
            reused_chip_count=outcome.reused_chip_count,
            rebuilt_chip_count=outcome.rebuilt_chip_count,
            reuse_rejected_count=outcome.reuse_rejected_count,
            base_drag_reused=refresh.base_drag_geometry_reused,
            had_base_drag_geometry=refresh.base_drag_chip_snapshot is not None,
        )
        self._preview_paint_snapshots.clear()
        active_placement = (
            self._landing_preview.attach_expected_landing_to_active_placement(
                self._landing_request.build()
            )
        )
        self._geometry.set_active_placement(active_placement)
        self._landing_preview.mark_initial_landing_shadow_ready(
            self._landing_request.build()
        )
        elapsed_ms = self._diagnostics.log_timing(
            "preview_geometry.total",
            started_at=started_at,
            gesture_id=self._metrics.gesture_id,
            event_id=self._metrics.event_id,
            preview_visual_count=len(outcome.publication.visuals_by_index),
            base_drag_geometry_count=(
                0
                if refresh.base_drag_chip_snapshot is None
                else len(refresh.base_drag_chip_snapshot.geometries_by_chip_index)
            ),
            visual_target_count=len(refresh.drop_target_visuals),
            lane_count=len(refresh.drop_target_lanes),
            preview_reused_visual_count=outcome.reused_chip_count,
            preview_rebuilt_visual_count=outcome.rebuilt_chip_count,
            base_drag_geometry_reused=refresh.base_drag_geometry_reused,
        )
        self._diagnostics.log_event(
            "preview_geometry.full_geometry_applied",
            gesture_id=self._metrics.gesture_id,
            event_id=self._metrics.event_id,
            elapsed_ms=f"{elapsed_ms:.3f}",
            has_preview_snapshot=preview_snapshot is not None,
            has_base_drag_snapshot=geometry_state.base_drag_snapshot is not None,
            active_target_kind=reorder_drag_target_kind(
                gesture_state.active_drop_target
            ),
        )
        if elapsed_ms >= _SLOW_PREVIEW_GEOMETRY_MS:
            self._diagnostics.log_event(
                "budget.preview_geometry_exceeded",
                gesture_id=self._metrics.gesture_id,
                event_id=self._metrics.event_id,
                elapsed_ms=f"{elapsed_ms:.3f}",
                threshold_ms=f"{_SLOW_PREVIEW_GEOMETRY_MS:.3f}",
                has_preview_snapshot=preview_snapshot is not None,
                has_base_drag_snapshot=geometry_state.base_drag_snapshot is not None,
            )
        return True


__all__ = ["PromptReorderPreviewGeometryRefreshOwner"]

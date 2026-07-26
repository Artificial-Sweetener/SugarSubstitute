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

"""Own pointer-selected reorder target transitions after hit testing."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPointF

from ..interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from ..projection.observability import (
    reorder_drag_started_at,
    reorder_drag_target_kind,
)
from .reorder_displacement_intent import ReorderDisplacementIntent
from .reorder_animation_presentation import PromptReorderAnimationPresentationOwner
from .reorder_drag_proxy_visual_owner import PromptReorderDragProxyVisualOwner
from .reorder_gesture_controller import PromptReorderGestureController
from .reorder_interaction_diagnostics import (
    PromptReorderInteractionDiagnosticsOwner,
)
from .reorder_landing_session import PromptReorderLandingSessionOwner
from .reorder_live_visual_owner import PromptReorderLiveVisualOwner
from .reorder_pointer_regions import PromptReorderPointerRegions
from .reorder_pointer_target_resolution import (
    PromptReorderPointerTargetResolutionOwner,
)
from .reorder_telemetry import PromptReorderTelemetry
from .reorder_visual_mode import PromptReorderVisualModeOwner
from .reorder_preview_visual_owner import PromptReorderPreviewVisualOwner
from .reorder_viewport_geometry import PromptReorderViewportGeometryOwner
from ..projection.reorder_interaction_geometry import PromptReorderInteractionGeometry


class PromptReorderPointerTargetTransitionOwner:
    """Resolve and apply one complete pointer-selected target transition."""

    def __init__(
        self,
        *,
        resolver: PromptReorderPointerTargetResolutionOwner,
        geometry: PromptReorderInteractionGeometry,
        gesture: PromptReorderGestureController,
        animation: PromptReorderAnimationPresentationOwner,
        live_visuals: PromptReorderLiveVisualOwner,
        preview_visuals: PromptReorderPreviewVisualOwner,
        regions: PromptReorderPointerRegions,
        drag_proxy: PromptReorderDragProxyVisualOwner,
        landing: PromptReorderLandingSessionOwner,
        viewport: PromptReorderViewportGeometryOwner,
        visual_mode: PromptReorderVisualModeOwner,
        preview_layout_changed: Callable[[], None],
        metrics: PromptReorderInteractionMetricsOwner,
        diagnostics: PromptReorderInteractionDiagnosticsOwner,
        telemetry: PromptReorderTelemetry,
    ) -> None:
        """Store focused transition collaborators and typed adapter ports."""

        self._resolver = resolver
        self._geometry = geometry
        self._gesture = gesture
        self._animation = animation
        self._live_visuals = live_visuals
        self._preview_visuals = preview_visuals
        self._regions = regions
        self._drag_proxy = drag_proxy
        self._landing = landing
        self._viewport = viewport
        self._visual_mode = visual_mode
        self._preview_layout_changed = preview_layout_changed
        self._metrics = metrics
        self._diagnostics = diagnostics
        self._telemetry = telemetry

    def update(
        self,
        local_pointer: QPointF,
        *,
        emit_preview_changed: bool = True,
    ) -> bool:
        """Resolve one pointer and publish work only when its target changes."""

        if self._gesture.state.dragged_segment_index is None:
            return False

        total_started_at = reorder_drag_started_at()
        previous_target = self._gesture.state.active_drop_target
        resolution = self._resolver.resolve(local_pointer)
        if resolution is None:
            return False
        if not resolution.changed:
            self._geometry.set_active_placement(resolution.active_placement)
            return False

        next_target = resolution.target
        resolve_elapsed_ms = self._resolver.last_resolve_elapsed_ms
        dragged_segment_index = self._gesture.state.dragged_segment_index
        segment_indices = tuple(self._regions.regions_by_index)
        preview_active = self._visual_mode.preview_active()
        live_visuals_by_index = self._live_visuals.visuals_by_index
        preview_visuals_by_index = self._preview_visuals.visuals_by_index
        phase_started_at = reorder_drag_started_at()
        self._geometry.update_preview_layout(
            dragged_segment_index=dragged_segment_index,
            active_target=next_target,
            viewport_identity=self._viewport.position_geometry_key(),
            gesture_id=self._metrics.gesture_id,
            event_id=self._metrics.event_id,
        )
        self._geometry.set_active_placement(resolution.active_placement)
        self._gesture.set_active_drop_target(next_target)
        if dragged_segment_index is not None:
            self._animation.record_target_change(
                ReorderDisplacementIntent(
                    source="pointer",
                    held_segment_index=dragged_segment_index,
                    target=next_target,
                    pointer_global_pos=(self._gesture.state.last_drag_global_position),
                    reason="pointer_target_changed",
                ),
                segment_indices=segment_indices,
                preview_active=preview_active,
                live_visuals_by_index=live_visuals_by_index,
                preview_visuals_by_index=preview_visuals_by_index,
            )
        self._drag_proxy.raise_proxy()
        self._diagnostics.log_timing(
            "drop_target.changed.preview_layout",
            started_at=phase_started_at,
            gesture_id=self._metrics.gesture_id,
            event_id=self._metrics.event_id,
            active_target_kind=reorder_drag_target_kind(
                self._gesture.state.active_drop_target
            ),
            ordered_count=len(self._geometry.state.ordered_segment_indices),
        )
        active_target = self._gesture.state.active_drop_target
        if (
            active_target is not None
            and self._geometry.state.preview_layout_view is None
        ):
            self._diagnostics.log_anomaly(
                "anomaly.target_changed_without_preview_update",
                previous_target_kind=reorder_drag_target_kind(previous_target),
                **self._telemetry.target_context(
                    active_target,
                    prefix="active_target",
                ),
            )
        if emit_preview_changed:
            phase_started_at = reorder_drag_started_at()
            self._preview_layout_changed()
            self._diagnostics.log_timing(
                "drop_target.changed.preview_signal",
                started_at=phase_started_at,
                gesture_id=self._metrics.gesture_id,
                event_id=self._metrics.event_id,
                active_target_kind=reorder_drag_target_kind(active_target),
            )
        geometry_state = self._geometry.state
        preview_geometry = geometry_state.preview_chip_geometry_snapshot
        self._diagnostics.log_event(
            "preview_state.surface_sync_requested",
            gesture_id=self._metrics.gesture_id,
            event_id=self._metrics.event_id,
            active_target_kind=reorder_drag_target_kind(active_target),
            has_preview_snapshot=geometry_state.preview_snapshot is not None,
            has_current_preview_geometry=(
                dragged_segment_index is not None
                and preview_geometry is not None
                and dragged_segment_index in preview_geometry.geometries_by_chip_index
            ),
            has_last_valid_shadow=(
                self._landing.publication.last_preview_geometry is not None
            ),
        )
        self._diagnostics.log_timing(
            "drop_target.total",
            started_at=total_started_at,
            gesture_id=self._metrics.gesture_id,
            event_id=self._metrics.event_id,
            target_changed=True,
            active_target_kind=reorder_drag_target_kind(active_target),
            resolve_elapsed_ms=f"{resolve_elapsed_ms:.3f}",
            ordered_count=len(geometry_state.ordered_segment_indices),
        )
        return True


__all__ = [
    "PromptReorderPointerTargetTransitionOwner",
]

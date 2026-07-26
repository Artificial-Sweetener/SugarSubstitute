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

"""Own allocation-neutral pointer target resolution and fast-path diagnostics."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from PySide6.QtCore import QPointF, QRectF, QSizeF

from ..interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from ..projection.observability import (
    reorder_drag_rect_context,
    reorder_drag_started_at,
    reorder_drag_target_kind,
)
from ..projection.reorder_interaction_geometry import PromptReorderInteractionGeometry
from ..projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)
from ..projection.reorder_pointer_hit_testing import (
    PromptReorderDropTargetResolution,
    PromptReorderDropTargetResolverInput,
    PromptReorderDropTargetTracker,
)
from .reorder_gesture_controller import PromptReorderGestureController
from .reorder_interaction_diagnostics import (
    PromptReorderInteractionDiagnosticsOwner,
)
from .reorder_telemetry import PromptReorderTelemetry


@dataclass(slots=True)
class PromptReorderPointerTargetResolutionOwner:
    """Resolve one pointer destination without publishing transition state."""

    geometry: PromptReorderInteractionGeometry
    gesture: PromptReorderGestureController
    metrics: PromptReorderInteractionMetricsOwner
    telemetry: PromptReorderTelemetry
    diagnostics: PromptReorderInteractionDiagnosticsOwner
    _tracker: PromptReorderDropTargetTracker = field(
        default_factory=PromptReorderDropTargetTracker
    )
    _last_resolve_elapsed_ms: float = field(default=0.0, init=False)

    @property
    def last_resolve_elapsed_ms(self) -> float:
        """Return the latest tracker duration for changed-target diagnostics."""

        return self._last_resolve_elapsed_ms

    def resolve(
        self,
        local_pointer: QPointF,
    ) -> PromptReorderDropTargetResolution | None:
        """Resolve one local pointer position without adding hot-path allocation."""

        dragged_segment_index = self.gesture.state.dragged_segment_index
        if dragged_segment_index is None:
            return None

        total_started_at = reorder_drag_started_at()
        previous_target = self.gesture.state.active_drop_target
        drag_rect = self._drag_intent_rect(local_pointer)
        phase_started_at = reorder_drag_started_at()
        geometry_state: PromptReorderInteractionGeometryState = self.geometry.state
        resolution = self._tracker.resolve(
            PromptReorderDropTargetResolverInput(
                drop_lanes=geometry_state.drop_target_lanes,
                target_visuals=geometry_state.drop_target_visuals,
                active_target=previous_target,
                drag_rect=drag_rect,
                geometry_generation_id=self.metrics.work_unit_id,
                placement_snapshot=geometry_state.placement_snapshot,
                active_placement=geometry_state.active_placement,
            ),
            gesture_id=self.metrics.gesture_id,
            event_id=self.metrics.event_id,
        )
        next_target = resolution.target
        pointer_sample = self.telemetry.should_log_pointer_event(
            move_count=self.metrics.drag_move_count,
            target_changed=resolution.changed,
        )
        if pointer_sample:
            resolve_elapsed_ms = self.diagnostics.log_timing(
                "drop_target.resolve",
                started_at=phase_started_at,
                gesture_id=self.metrics.gesture_id,
                event_id=self.metrics.event_id,
                previous_target_kind=reorder_drag_target_kind(previous_target),
                next_target_kind=reorder_drag_target_kind(next_target),
                target_changed=resolution.changed,
                lane_count=len(geometry_state.drop_target_lanes),
                visual_target_count=len(geometry_state.drop_target_visuals),
                **reorder_drag_rect_context(drag_rect, prefix="intent"),
            )
        else:
            resolve_elapsed_ms = (time.perf_counter() - phase_started_at) * 1000.0
        self._last_resolve_elapsed_ms = resolve_elapsed_ms
        if resolution.no_lane and geometry_state.base_drag_layout_view is not None:
            self.diagnostics.log_anomaly(
                "anomaly.no_drop_lanes_after_base_drag_ready",
                base_row_count=len(geometry_state.base_drag_layout_view.rows),
                base_gap_count=len(geometry_state.base_drag_layout_view.gaps),
                has_base_snapshot=geometry_state.base_drag_snapshot is not None,
                **reorder_drag_rect_context(drag_rect, prefix="intent"),
            )
        self.metrics.record_drop_target_resolution(
            changed=resolution.changed,
            no_lane=resolution.no_lane,
        )
        if not resolution.changed:
            if pointer_sample:
                self.diagnostics.log_event(
                    "drop_target.no_change_fast_path",
                    gesture_id=self.metrics.gesture_id,
                    event_id=self.metrics.event_id,
                    active_target_kind=reorder_drag_target_kind(previous_target),
                    resolve_elapsed_ms=f"{resolve_elapsed_ms:.3f}",
                )
                self.diagnostics.log_timing(
                    "drop_target.total",
                    started_at=total_started_at,
                    gesture_id=self.metrics.gesture_id,
                    event_id=self.metrics.event_id,
                    target_changed=False,
                    active_target_kind=reorder_drag_target_kind(previous_target),
                    resolve_elapsed_ms=f"{resolve_elapsed_ms:.3f}",
                )
            return resolution

        self.diagnostics.log_event(
            "drop_target.changed_rebuild_path",
            gesture_id=self.metrics.gesture_id,
            event_id=self.metrics.event_id,
            previous_target_kind=reorder_drag_target_kind(previous_target),
            next_target_kind=reorder_drag_target_kind(next_target),
            resolve_elapsed_ms=f"{resolve_elapsed_ms:.3f}",
        )
        return resolution

    def _drag_intent_rect(self, local_pointer: QPointF) -> QRectF:
        """Return the logical held-chip rect used by target resolution."""

        size = self.gesture.state.drag_intent_size
        if size is None or size.isEmpty():
            size = QSizeF(1.0, 1.0)
        grab_offset = self.gesture.state.drag_grab_offset
        if grab_offset is None:
            grab_offset = QPointF(size.width() / 2.0, size.height() / 2.0)
        intent_rect = QRectF(local_pointer - grab_offset, size)
        self.gesture.set_last_drag_intent_rect(intent_rect)
        return intent_rect


__all__ = [
    "PromptReorderPointerTargetResolutionOwner",
]

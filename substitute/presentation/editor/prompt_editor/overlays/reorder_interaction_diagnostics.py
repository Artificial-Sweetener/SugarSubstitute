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

"""Own prompt-safe reorder interaction diagnostics and gesture summaries."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from ..interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from ..projection.reorder_chip_geometry import PromptReorderChipGeometrySnapshot
from ..projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)
from .reorder_landing_models import PromptReorderLandingShadowCounters


class PromptReorderInteractionTelemetry(Protocol):
    """Expose validated logging operations used by interaction diagnostics."""

    def log_event(self, event: str, **context: object) -> None:
        """Log one prompt-safe structural event."""

    def log_timing(
        self,
        event: str,
        *,
        started_at: float,
        **context: object,
    ) -> float:
        """Log one prompt-safe timing event."""

    def log_slow_path_if_needed(
        self,
        event: str,
        *,
        elapsed_ms: float,
        threshold_ms: float,
        gesture_id: int | None,
        event_id: int | None,
        **context: object,
    ) -> None:
        """Log one correlated budget overrun when required."""


@dataclass(frozen=True, slots=True)
class PromptReorderGestureSummaryContext:
    """Carry non-instrumentation facts needed for one gesture summary."""

    outcome: str
    chip_geometry_count: int
    preview_chip_geometry_count: int
    expected_chip_count: int
    placement_geometry_count: int
    landing_counters: PromptReorderLandingShadowCounters
    owner_counters: Mapping[str, object]


class PromptReorderInteractionDiagnosticsOwner:
    """Coordinate validated events with authoritative interaction metrics."""

    def __init__(
        self,
        *,
        telemetry: PromptReorderInteractionTelemetry,
        metrics: PromptReorderInteractionMetricsOwner,
    ) -> None:
        """Bind prompt-safe logging and gesture metric authorities."""

        self._telemetry = telemetry
        self._metrics = metrics

    def log_event(self, event: str, **context: object) -> None:
        """Emit one validated prompt-safe interaction event."""

        self._telemetry.log_event(event, **context)

    def log_timing(
        self,
        event: str,
        *,
        started_at: float,
        **context: object,
    ) -> float:
        """Emit one validated timing event and return elapsed milliseconds."""

        return self._telemetry.log_timing(
            event,
            started_at=started_at,
            **context,
        )

    def log_slow_path_if_needed(
        self,
        event: str,
        *,
        elapsed_ms: float,
        threshold_ms: float,
        **context: object,
    ) -> None:
        """Emit a correlated slow-path event only after its budget is exceeded."""

        self._telemetry.log_slow_path_if_needed(
            event,
            elapsed_ms=elapsed_ms,
            threshold_ms=threshold_ms,
            gesture_id=self._metrics.gesture_id,
            event_id=self._metrics.event_id,
            **context,
        )

    def log_anomaly(self, event: str, **context: object) -> None:
        """Count and emit one unexpected visual or placement outcome."""

        self._metrics.record_anomaly()
        self._telemetry.log_event(
            event,
            gesture_id=self._metrics.gesture_id,
            event_id=self._metrics.event_id,
            **context,
        )

    def log_expected_geometry(self, event: str, **context: object) -> None:
        """Count and emit one expected diagnostic geometry outcome."""

        self._metrics.record_expected_diagnostic()
        self._telemetry.log_event(
            event,
            gesture_id=self._metrics.gesture_id,
            event_id=self._metrics.event_id,
            **context,
        )

    def record_pointer_unexpected_work(
        self,
        work: str,
        **context: object,
    ) -> None:
        """Count and emit expensive work only while the pointer loop is active."""

        if not self._metrics.record_pointer_unexpected_work(work):
            return
        self._telemetry.log_event(
            "pointer_loop.unexpected_work",
            gesture_id=self._metrics.gesture_id,
            event_id=self._metrics.event_id,
            work=work,
            **context,
        )

    def log_gesture_summary(
        self,
        context: PromptReorderGestureSummaryContext,
    ) -> None:
        """Emit one compact summary from immutable owner publications."""

        metrics = self._metrics.snapshot()
        landing = context.landing_counters
        missing_geometry_count = max(
            0,
            context.expected_chip_count - context.chip_geometry_count,
        )
        self._telemetry.log_event(
            "gesture_summary",
            gesture_id=metrics.gesture_id,
            event_id=metrics.event_id,
            outcome=context.outcome,
            move_count=metrics.drag_move_count,
            target_change_count=metrics.target_change_count,
            placement_change_count=metrics.target_change_count,
            drop_target_no_change_count=metrics.drop_target_no_change_count,
            drop_target_changed_count=metrics.drop_target_changed_count,
            preview_sync_immediate_count=metrics.preview_sync_immediate_count,
            preview_sync_deferred_count=metrics.preview_sync_deferred_count,
            pointer_unexpected_work_count=metrics.pointer_unexpected_work_count,
            pointer_preview_rebuild_count=metrics.pointer_preview_rebuild_count,
            pointer_full_refresh_count=metrics.pointer_full_refresh_count,
            pointer_base_cache_miss_count=metrics.pointer_base_cache_miss_count,
            pointer_paint_request_count=metrics.pointer_paint_request_count,
            refresh_work_unit_count=metrics.refresh_work_unit_count,
            skipped_refresh_count=metrics.skipped_refresh_count,
            overlay_position_skip_count=metrics.position_refresh_skip_count,
            overlay_position_run_count=metrics.position_refresh_run_count,
            preview_scheduler_request_count=metrics.preview_scheduler_request_count,
            preview_scheduler_run_count=metrics.preview_scheduler_run_count,
            preview_scheduler_stale_skip_count=(
                metrics.preview_scheduler_stale_skip_count
            ),
            preview_geometry_suppressed_count=(
                metrics.preview_geometry_suppressed_count
            ),
            preview_geometry_full_count=metrics.preview_geometry_full_count,
            initial_shadow_sync_count=landing.initial_shadow_sync_count,
            initial_shadow_ready_count=landing.initial_shadow_ready_count,
            stale_shadow_rejected_count=landing.stale_shadow_rejected_count,
            base_drag_geometry_reuse_count=metrics.base_drag_geometry_reuse_count,
            base_drag_geometry_rebuild_count=metrics.base_drag_geometry_rebuild_count,
            preview_geometry_reused_chip_count=(
                metrics.preview_geometry_reused_chip_count
            ),
            preview_geometry_rebuilt_chip_count=(
                metrics.preview_geometry_rebuilt_chip_count
            ),
            preview_geometry_reuse_rejected_count=(
                metrics.preview_geometry_reuse_rejected_count
            ),
            held_shadow_capture_count=landing.held_shadow_capture_count,
            held_shadow_missing_count=landing.held_shadow_missing_count,
            pending_shadow_fallback_count=landing.pending_shadow_fallback_count,
            pending_shadow_replaced_marker_count=(
                landing.pending_shadow_replaced_marker_count
            ),
            marker_fallback_count=metrics.marker_fallback_count,
            diagnostic_expected_offset_count=(
                metrics.expected_diagnostic_count + landing.expected_diagnostic_count
            ),
            no_lane_count=metrics.no_lane_count,
            anomaly_count=metrics.anomaly_count + landing.anomaly_count,
            split_shadow_count=metrics.split_shadow_count,
            chip_geometry_count=context.chip_geometry_count,
            preview_chip_geometry_count=context.preview_chip_geometry_count,
            expected_chip_count=context.expected_chip_count,
            chip_geometry_missing_count=missing_geometry_count,
            chip_geometry_duplicate_count=0,
            chip_geometry_mismatch_count=0,
            placement_geometry_count=context.placement_geometry_count,
            max_drag_move_ms=f"{metrics.max_drag_move_ms:.3f}",
            max_preview_sync_ms=f"{metrics.max_preview_sync_ms:.3f}",
            max_live_visuals_ms=f"{metrics.max_live_visuals_ms:.3f}",
            max_render_plan_ms=f"{metrics.max_render_plan_ms:.3f}",
            **context.owner_counters,
        )

    def log_gesture_summary_from_publications(
        self,
        *,
        outcome: str,
        chip_geometry: PromptReorderChipGeometrySnapshot | None,
        geometry: PromptReorderInteractionGeometryState,
        expected_chip_count: int,
        landing_counters: PromptReorderLandingShadowCounters,
        owner_counters: Mapping[str, object],
    ) -> None:
        """Summarize one gesture directly from immutable owner publications."""

        preview_geometry = geometry.preview_chip_geometry_snapshot
        placement = geometry.placement_snapshot
        self.log_gesture_summary(
            PromptReorderGestureSummaryContext(
                outcome=outcome,
                chip_geometry_count=(
                    0
                    if chip_geometry is None
                    else len(chip_geometry.geometries_by_chip_index)
                ),
                preview_chip_geometry_count=(
                    0
                    if preview_geometry is None
                    else len(preview_geometry.geometries_by_chip_index)
                ),
                expected_chip_count=expected_chip_count,
                placement_geometry_count=(
                    0 if placement is None else len(placement.placements)
                ),
                landing_counters=landing_counters,
                owner_counters=owner_counters,
            )
        )

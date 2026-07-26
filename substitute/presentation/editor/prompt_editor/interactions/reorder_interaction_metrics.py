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

"""Own reorder gesture identities, structural counters, and timing maxima."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PromptReorderInteractionMetricsSnapshot:
    """Publish immutable diagnostics for one current or completed gesture."""

    gesture_id: int | None = None
    event_id: int | None = None
    drag_move_count: int = 0
    target_change_count: int = 0
    drop_target_no_change_count: int = 0
    drop_target_changed_count: int = 0
    no_lane_count: int = 0
    anomaly_count: int = 0
    split_shadow_count: int = 0
    preview_sync_immediate_count: int = 0
    preview_sync_deferred_count: int = 0
    pointer_unexpected_work_count: int = 0
    pointer_preview_rebuild_count: int = 0
    pointer_full_refresh_count: int = 0
    pointer_base_cache_miss_count: int = 0
    pointer_paint_request_count: int = 0
    refresh_work_unit_count: int = 0
    skipped_refresh_count: int = 0
    expected_diagnostic_count: int = 0
    position_refresh_skip_count: int = 0
    position_refresh_run_count: int = 0
    preview_scheduler_request_count: int = 0
    preview_scheduler_run_count: int = 0
    preview_scheduler_stale_skip_count: int = 0
    preview_geometry_suppressed_count: int = 0
    preview_geometry_full_count: int = 0
    base_drag_geometry_reuse_count: int = 0
    base_drag_geometry_rebuild_count: int = 0
    preview_geometry_reused_chip_count: int = 0
    preview_geometry_rebuilt_chip_count: int = 0
    preview_geometry_reuse_rejected_count: int = 0
    marker_fallback_count: int = 0
    work_unit_id: int = 0
    pointer_loop_depth: int = 0
    max_drag_move_ms: float = 0.0
    max_live_visuals_ms: float = 0.0
    max_preview_sync_ms: float = 0.0
    max_render_plan_ms: float = 0.0


class PromptReorderInteractionMetricsOwner:
    """Own constant-time gesture instrumentation without instrumenting paint."""

    def __init__(self) -> None:
        """Initialize empty instrumentation state."""

        self.begin_session()

    def begin_session(self) -> None:
        """Reset metrics before publishing geometry for a new reorder session."""

        self._gesture_id: int | None = None
        self._event_id: int | None = None
        self._next_event_id = 0
        self._drag_move_count = 0
        self._target_change_count = 0
        self._drop_target_no_change_count = 0
        self._drop_target_changed_count = 0
        self._no_lane_count = 0
        self._anomaly_count = 0
        self._split_shadow_count = 0
        self._preview_sync_immediate_count = 0
        self._preview_sync_deferred_count = 0
        self._pointer_unexpected_work_count = 0
        self._pointer_preview_rebuild_count = 0
        self._pointer_full_refresh_count = 0
        self._pointer_base_cache_miss_count = 0
        self._pointer_paint_request_count = 0
        self._refresh_work_unit_count = 0
        self._skipped_refresh_count = 0
        self._expected_diagnostic_count = 0
        self._position_refresh_skip_count = 0
        self._position_refresh_run_count = 0
        self._preview_scheduler_request_count = 0
        self._preview_scheduler_run_count = 0
        self._preview_scheduler_stale_skip_count = 0
        self._preview_geometry_suppressed_count = 0
        self._preview_geometry_full_count = 0
        self._base_drag_geometry_reuse_count = 0
        self._base_drag_geometry_rebuild_count = 0
        self._preview_geometry_reused_chip_count = 0
        self._preview_geometry_rebuilt_chip_count = 0
        self._preview_geometry_reuse_rejected_count = 0
        self._marker_fallback_count = 0
        self._work_unit_id = 0
        self._pointer_loop_depth = 0
        self._max_drag_move_ms = 0.0
        self._max_live_visuals_ms = 0.0
        self._max_preview_sync_ms = 0.0
        self._max_render_plan_ms = 0.0

    @property
    def gesture_id(self) -> int | None:
        """Return the active gesture identifier."""

        return self._gesture_id

    @property
    def event_id(self) -> int | None:
        """Return the latest event identifier in the active gesture."""

        return self._event_id

    @property
    def drag_move_count(self) -> int:
        """Return the active gesture's pointer-move count."""

        return self._drag_move_count

    @property
    def work_unit_id(self) -> int:
        """Return the latest correlated structural work-unit identifier."""

        return self._work_unit_id

    @property
    def pointer_loop_active(self) -> bool:
        """Return whether protected pointer processing is active."""

        return self._pointer_loop_depth > 0

    def begin_gesture(self, gesture_id: int) -> int:
        """Reset all per-gesture state and begin the first event."""

        self.begin_session()
        self._gesture_id = gesture_id
        return self.begin_event()

    def finish_gesture(self) -> None:
        """End identity publication while retaining completed diagnostics."""

        self._gesture_id = None
        self._event_id = None
        self._pointer_loop_depth = 0

    def begin_event(self) -> int:
        """Advance and return the current gesture event identifier."""

        self._next_event_id += 1
        self._event_id = self._next_event_id
        return self._next_event_id

    def next_work_unit(self) -> int:
        """Advance and return the correlated structural work-unit identifier."""

        self._work_unit_id += 1
        return self._work_unit_id

    def begin_pointer_move(self) -> int:
        """Record one pointer move and enter the protected pointer loop."""

        self._drag_move_count += 1
        self._pointer_loop_depth += 1
        return self._drag_move_count

    def leave_pointer_loop(self) -> None:
        """Leave protected pointer processing, including exceptional exits."""

        self._pointer_loop_depth = max(0, self._pointer_loop_depth - 1)

    def record_pointer_move_outcome(
        self,
        *,
        elapsed_ms: float,
        target_changed: bool,
    ) -> None:
        """Retain timing and target-change results after pointer processing."""

        self._max_drag_move_ms = max(self._max_drag_move_ms, elapsed_ms)
        if target_changed:
            self._target_change_count += 1

    def record_refresh_work_unit(self) -> None:
        """Record one requested overlay refresh work unit."""

        self._refresh_work_unit_count += 1

    def record_skipped_refresh(self) -> None:
        """Record one overlay refresh that reused already-current state."""

        self._skipped_refresh_count += 1

    def record_position_refresh(self, *, changed: bool) -> None:
        """Record whether overlay position geometry changed."""

        if changed:
            self._position_refresh_run_count += 1
        else:
            self._position_refresh_skip_count += 1

    def record_preview_sync_decision(self, immediate: bool) -> None:
        """Record one preview synchronization scheduling decision."""

        if immediate:
            self._preview_sync_immediate_count += 1
        else:
            self._preview_sync_deferred_count += 1

    def record_preview_scheduler(self, event: str) -> None:
        """Record one latest-wins preview scheduler outcome."""

        if event == "requested":
            self._preview_scheduler_request_count += 1
        elif event == "ran_latest":
            self._preview_scheduler_run_count += 1
        elif event == "skipped_stale":
            self._preview_scheduler_stale_skip_count += 1

    def record_pointer_unexpected_work(
        self,
        work: str,
    ) -> bool:
        """Record prohibited pointer-loop work and return whether it was active."""

        if not self.pointer_loop_active:
            return False
        self._pointer_unexpected_work_count += 1
        if work == "preview_rebuild":
            self._pointer_preview_rebuild_count += 1
        elif work == "full_refresh":
            self._pointer_full_refresh_count += 1
        elif work == "base_cache_miss":
            self._pointer_base_cache_miss_count += 1
        elif work == "paint_request":
            self._pointer_paint_request_count += 1
        return True

    def record_preview_geometry_suppressed(self) -> None:
        """Record reuse of already-current preview geometry."""

        self._preview_geometry_suppressed_count += 1

    def record_preview_geometry_build(
        self,
        *,
        reused_chip_count: int,
        rebuilt_chip_count: int,
        reuse_rejected_count: int,
        base_drag_reused: bool,
        had_base_drag_geometry: bool,
    ) -> None:
        """Record one full preview-geometry build and its reuse outcome."""

        self._preview_geometry_full_count += 1
        self._preview_geometry_reused_chip_count += reused_chip_count
        self._preview_geometry_rebuilt_chip_count += rebuilt_chip_count
        self._preview_geometry_reuse_rejected_count += reuse_rejected_count
        if base_drag_reused:
            self._base_drag_geometry_reuse_count += 1
        elif had_base_drag_geometry:
            self._base_drag_geometry_rebuild_count += 1

    def record_drop_target_resolution(
        self,
        *,
        changed: bool,
        no_lane: bool,
    ) -> None:
        """Record one pointer target resolution result."""

        if no_lane:
            self._no_lane_count += 1
        if changed:
            self._drop_target_changed_count += 1
        else:
            self._drop_target_no_change_count += 1

    def record_anomaly(self) -> None:
        """Record one unexpected visual or placement outcome."""

        self._anomaly_count += 1

    def record_expected_diagnostic(self) -> None:
        """Record one expected but diagnostically useful geometry outcome."""

        self._expected_diagnostic_count += 1

    def record_marker_fallback(self) -> None:
        """Record one insertion-marker fallback."""

        self._marker_fallback_count += 1

    def record_live_visuals_elapsed(self, elapsed_ms: float) -> None:
        """Retain the maximum live-visual preparation duration."""

        self._max_live_visuals_ms = max(self._max_live_visuals_ms, elapsed_ms)

    def record_preview_sync_elapsed(self, elapsed_ms: float) -> None:
        """Retain the maximum preview synchronization duration."""

        self._max_preview_sync_ms = max(self._max_preview_sync_ms, elapsed_ms)

    def record_render_plan_elapsed(self, elapsed_ms: float) -> None:
        """Retain the maximum reorder render-plan duration."""

        self._max_render_plan_ms = max(self._max_render_plan_ms, elapsed_ms)

    def snapshot(self) -> PromptReorderInteractionMetricsSnapshot:
        """Return immutable diagnostics without affecting interaction work."""

        return PromptReorderInteractionMetricsSnapshot(
            gesture_id=self._gesture_id,
            event_id=self._event_id,
            drag_move_count=self._drag_move_count,
            target_change_count=self._target_change_count,
            drop_target_no_change_count=self._drop_target_no_change_count,
            drop_target_changed_count=self._drop_target_changed_count,
            no_lane_count=self._no_lane_count,
            anomaly_count=self._anomaly_count,
            split_shadow_count=self._split_shadow_count,
            preview_sync_immediate_count=self._preview_sync_immediate_count,
            preview_sync_deferred_count=self._preview_sync_deferred_count,
            pointer_unexpected_work_count=self._pointer_unexpected_work_count,
            pointer_preview_rebuild_count=self._pointer_preview_rebuild_count,
            pointer_full_refresh_count=self._pointer_full_refresh_count,
            pointer_base_cache_miss_count=self._pointer_base_cache_miss_count,
            pointer_paint_request_count=self._pointer_paint_request_count,
            refresh_work_unit_count=self._refresh_work_unit_count,
            skipped_refresh_count=self._skipped_refresh_count,
            expected_diagnostic_count=self._expected_diagnostic_count,
            position_refresh_skip_count=self._position_refresh_skip_count,
            position_refresh_run_count=self._position_refresh_run_count,
            preview_scheduler_request_count=self._preview_scheduler_request_count,
            preview_scheduler_run_count=self._preview_scheduler_run_count,
            preview_scheduler_stale_skip_count=(
                self._preview_scheduler_stale_skip_count
            ),
            preview_geometry_suppressed_count=(self._preview_geometry_suppressed_count),
            preview_geometry_full_count=self._preview_geometry_full_count,
            base_drag_geometry_reuse_count=self._base_drag_geometry_reuse_count,
            base_drag_geometry_rebuild_count=self._base_drag_geometry_rebuild_count,
            preview_geometry_reused_chip_count=(
                self._preview_geometry_reused_chip_count
            ),
            preview_geometry_rebuilt_chip_count=(
                self._preview_geometry_rebuilt_chip_count
            ),
            preview_geometry_reuse_rejected_count=(
                self._preview_geometry_reuse_rejected_count
            ),
            marker_fallback_count=self._marker_fallback_count,
            work_unit_id=self._work_unit_id,
            pointer_loop_depth=self._pointer_loop_depth,
            max_drag_move_ms=self._max_drag_move_ms,
            max_live_visuals_ms=self._max_live_visuals_ms,
            max_preview_sync_ms=self._max_preview_sync_ms,
            max_render_plan_ms=self._max_render_plan_ms,
        )

    def performance_counters(self) -> dict[str, int | float]:
        """Return the stable harness counter schema."""

        snapshot = self.snapshot()
        return {
            "drag_move_count": snapshot.drag_move_count,
            "target_change_count": snapshot.target_change_count,
            "drop_target_no_change_count": snapshot.drop_target_no_change_count,
            "drop_target_changed_count": snapshot.drop_target_changed_count,
            "preview_geometry_full_count": snapshot.preview_geometry_full_count,
            "pointer_unexpected_work_count": snapshot.pointer_unexpected_work_count,
            "pointer_preview_rebuild_count": snapshot.pointer_preview_rebuild_count,
            "pointer_full_refresh_count": snapshot.pointer_full_refresh_count,
            "pointer_base_cache_miss_count": snapshot.pointer_base_cache_miss_count,
            "pointer_paint_request_count": snapshot.pointer_paint_request_count,
            "preview_scheduler_request_count": (
                snapshot.preview_scheduler_request_count
            ),
            "preview_scheduler_run_count": snapshot.preview_scheduler_run_count,
            "max_drag_move_ms": snapshot.max_drag_move_ms,
            "max_preview_sync_ms": snapshot.max_preview_sync_ms,
            "max_live_visuals_ms": snapshot.max_live_visuals_ms,
            "max_render_plan_ms": snapshot.max_render_plan_ms,
        }

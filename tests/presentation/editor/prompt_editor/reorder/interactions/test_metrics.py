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

"""Verify sole ownership of prompt-reorder gesture metrics and budgets."""

from __future__ import annotations

from substitute.presentation.editor.prompt_editor.interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)


def test_interaction_metrics_own_gesture_event_and_pointer_lifecycle() -> None:
    """One owner should reset identities and retain completed gesture evidence."""

    owner = PromptReorderInteractionMetricsOwner()

    assert owner.begin_gesture(41) == 1
    assert owner.begin_event() == 2
    assert owner.next_work_unit() == 1
    assert owner.begin_pointer_move() == 1
    assert owner.pointer_loop_active
    assert owner.record_pointer_unexpected_work("preview_rebuild")
    owner.leave_pointer_loop()
    owner.record_pointer_move_outcome(elapsed_ms=7.5, target_changed=True)
    owner.finish_gesture()

    snapshot = owner.snapshot()
    assert snapshot.gesture_id is None
    assert snapshot.event_id is None
    assert snapshot.drag_move_count == 1
    assert snapshot.target_change_count == 1
    assert snapshot.pointer_unexpected_work_count == 1
    assert snapshot.pointer_preview_rebuild_count == 1
    assert snapshot.pointer_loop_depth == 0
    assert snapshot.max_drag_move_ms == 7.5

    assert owner.begin_gesture(42) == 1
    assert owner.snapshot().gesture_id == 42
    assert owner.performance_counters()["drag_move_count"] == 0


def test_interaction_metrics_classify_structural_work_without_hot_path_scans() -> None:
    """Constant-time record methods should preserve the harness counter schema."""

    owner = PromptReorderInteractionMetricsOwner()
    owner.begin_gesture(5)
    owner.record_refresh_work_unit()
    owner.record_skipped_refresh()
    owner.record_position_refresh(changed=False)
    owner.record_position_refresh(changed=True)
    owner.record_preview_sync_decision(immediate=True)
    owner.record_preview_sync_decision(immediate=False)
    owner.record_preview_scheduler("requested")
    owner.record_preview_scheduler("ran_latest")
    owner.record_preview_scheduler("skipped_stale")
    owner.record_preview_geometry_suppressed()
    owner.record_preview_geometry_build(
        reused_chip_count=3,
        rebuilt_chip_count=2,
        reuse_rejected_count=1,
        base_drag_reused=False,
        had_base_drag_geometry=True,
    )
    owner.record_drop_target_resolution(changed=False, no_lane=True)
    owner.record_drop_target_resolution(changed=True, no_lane=False)
    owner.record_anomaly()
    owner.record_expected_diagnostic()
    owner.record_marker_fallback()
    owner.record_live_visuals_elapsed(4.0)
    owner.record_preview_sync_elapsed(5.0)
    owner.record_render_plan_elapsed(6.0)

    snapshot = owner.snapshot()
    assert snapshot.refresh_work_unit_count == 1
    assert snapshot.skipped_refresh_count == 1
    assert snapshot.position_refresh_skip_count == 1
    assert snapshot.position_refresh_run_count == 1
    assert snapshot.preview_sync_immediate_count == 1
    assert snapshot.preview_sync_deferred_count == 1
    assert snapshot.preview_scheduler_request_count == 1
    assert snapshot.preview_scheduler_run_count == 1
    assert snapshot.preview_scheduler_stale_skip_count == 1
    assert snapshot.preview_geometry_suppressed_count == 1
    assert snapshot.preview_geometry_full_count == 1
    assert snapshot.preview_geometry_reused_chip_count == 3
    assert snapshot.preview_geometry_rebuilt_chip_count == 2
    assert snapshot.preview_geometry_reuse_rejected_count == 1
    assert snapshot.base_drag_geometry_rebuild_count == 1
    assert snapshot.drop_target_no_change_count == 1
    assert snapshot.drop_target_changed_count == 1
    assert snapshot.no_lane_count == 1
    assert snapshot.anomaly_count == 1
    assert snapshot.expected_diagnostic_count == 1
    assert snapshot.marker_fallback_count == 1
    assert snapshot.max_live_visuals_ms == 4.0
    assert snapshot.max_preview_sync_ms == 5.0
    assert snapshot.max_render_plan_ms == 6.0
    assert not owner.record_pointer_unexpected_work("paint_request")


def test_interaction_metrics_reset_before_new_session_geometry() -> None:
    """A new overlay session must not inherit completed-session work counters."""

    owner = PromptReorderInteractionMetricsOwner()
    owner.record_refresh_work_unit()
    owner.record_preview_geometry_build(
        reused_chip_count=1,
        rebuilt_chip_count=2,
        reuse_rejected_count=0,
        base_drag_reused=False,
        had_base_drag_geometry=False,
    )

    owner.begin_session()

    snapshot = owner.snapshot()
    assert snapshot.refresh_work_unit_count == 0
    assert snapshot.preview_geometry_full_count == 0
    assert snapshot.preview_geometry_reused_chip_count == 0
    assert snapshot.preview_geometry_rebuilt_chip_count == 0

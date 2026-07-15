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

"""Coordinate reorder overlay drag and keyboard interactions."""

# mypy: disable-error-code="assignment,has-type,no-any-return,var-annotated"
# This mixin intentionally uses state initialized by SegmentReorderOverlay; the
# suppressions keep the Qt shell split without inventing duplicate state owners.

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QPoint

from substitute.application.prompt_editor import PromptReorderDropTarget

from ..projection.observability import (
    next_reorder_drag_gesture_id,
    reorder_drag_started_at,
    reorder_drag_target_kind,
)
from .reorder_gesture_controller import (
    PromptReorderCancelIntent,
    PromptReorderCommitIntent,
    PromptReorderDragIntent,
)
from .reorder_displacement_intent import ReorderDisplacementIntent

if TYPE_CHECKING:
    from .reorder_overlay import _SegmentChip

_SLOW_DRAG_MOVE_MS = 16.0


class _OverlayShellAccess:
    """Provide dynamic access to state initialized by the concrete overlay shell."""

    def __getattr__(self, name: str) -> Any:
        """Defer shell-owned attribute lookup to the concrete overlay instance."""

        raise AttributeError(name)


class PromptReorderOverlayInteractionMixin(_OverlayShellAccess):
    """Own overlay gesture orchestration while delegating policy to collaborators."""

    def move_active_chip_left(self) -> bool:
        """Move the active chip to the previous visible populated-row slot."""

        return self._move_active_chip_by_keyboard(horizontal_step=-1)

    def move_active_chip_right(self) -> bool:
        """Move the active chip to the next visible populated-row slot."""

        return self._move_active_chip_by_keyboard(horizontal_step=1)

    def move_active_chip_up(self) -> bool:
        """Move the active chip to the nearest slot or blank-line lane above."""

        return self._move_active_chip_by_keyboard(vertical_direction=-1)

    def move_active_chip_down(self) -> bool:
        """Move the active chip to the nearest slot or blank-line lane below."""

        return self._move_active_chip_by_keyboard(vertical_direction=1)

    def start_drag(
        self,
        chip: _SegmentChip,
        *,
        global_pos: QPoint,
        press_global_pos: QPoint,
    ) -> None:
        """Begin dragging the supplied segment hotspot."""

        if self._gesture.state.dragged_segment_index is not None:
            return

        current_layout_view = self._current_layout_view
        document_view = self._document_view
        if current_layout_view is None or document_view is None:
            return
        self._emit_drag_intent(
            PromptReorderDragIntent(
                phase="start",
                segment_index=chip.segment_index,
                global_position=global_pos,
            )
        )

        gesture_id = next_reorder_drag_gesture_id()
        self._instrumentation_gesture_id = gesture_id
        self._instrumentation_next_event_id = 0
        event_id = self._begin_instrumented_drag_event()
        self._instrumentation_drag_move_count = 0
        self._instrumentation_target_change_count = 0
        self._instrumentation_drop_target_no_change_count = 0
        self._instrumentation_drop_target_changed_count = 0
        self._instrumentation_no_lane_count = 0
        self._instrumentation_anomaly_count = 0
        self._instrumentation_split_shadow_count = 0
        self._instrumentation_preview_sync_immediate_count = 0
        self._instrumentation_preview_sync_deferred_count = 0
        self._instrumentation_pointer_unexpected_work_count = 0
        self._instrumentation_pointer_preview_rebuild_count = 0
        self._instrumentation_pointer_full_refresh_count = 0
        self._instrumentation_pointer_base_cache_miss_count = 0
        self._instrumentation_pointer_paint_request_count = 0
        self._instrumentation_refresh_work_unit_count = 0
        self._instrumentation_skipped_refresh_count = 0
        self._instrumentation_expected_diagnostic_count = 0
        self._instrumentation_position_refresh_skip_count = 0
        self._instrumentation_position_refresh_run_count = 0
        self._instrumentation_preview_scheduler_request_count = 0
        self._instrumentation_preview_scheduler_run_count = 0
        self._instrumentation_preview_scheduler_stale_skip_count = 0
        self._instrumentation_autoscroll_schedule_count = 0
        self._instrumentation_autoscroll_coalesced_count = 0
        self._instrumentation_autoscroll_flush_count = 0
        self._instrumentation_autoscroll_target_refresh_count = 0
        self._instrumentation_preview_geometry_suppressed_count = 0
        self._instrumentation_preview_geometry_full_count = 0
        self._instrumentation_base_drag_geometry_reuse_count = 0
        self._instrumentation_base_drag_geometry_rebuild_count = 0
        self._instrumentation_preview_geometry_reused_chip_count = 0
        self._instrumentation_preview_geometry_rebuilt_chip_count = 0
        self._instrumentation_preview_geometry_reuse_rejected_count = 0
        self._instrumentation_marker_fallback_count = 0
        self._instrumentation_work_unit_id = 0
        self._pointer_loop_depth = 0
        self._instrumentation_max_drag_move_ms = 0.0
        self._instrumentation_max_live_visuals_ms = 0.0
        self._instrumentation_max_preview_sync_ms = 0.0
        self._instrumentation_max_render_plan_ms = 0.0
        self._editor.reset_reorder_geometry_cache_counters()
        self._drag_proxy_state_factory.reset_drag_session()
        self._autoscroll.reset_counters()
        self._clear_pending_autoscroll_invalidation()
        total_started_at = reorder_drag_started_at()
        self._log_interaction_event(
            "start",
            gesture_id=gesture_id,
            event_id=event_id,
            dragged_segment_index=chip.segment_index,
            segment_count=len(self._segments_by_index),
            row_count=len(current_layout_view.rows),
            gap_count=len(current_layout_view.gaps),
            ordered_count=len(self._ordered_segment_indices),
        )
        self._gesture.begin_pointer_drag(
            segment_index=chip.segment_index,
            global_position=global_pos,
        )
        phase_started_at = reorder_drag_started_at()
        self._base_drag_layout_view = self._geometry.begin_drag(
            dragged_segment_index=chip.segment_index,
            gesture_id=gesture_id,
            event_id=event_id,
        )
        if self._base_drag_layout_view is None:
            return
        self._base_drag_reorder_state = self._geometry.base_drag_reorder_state
        self._log_interaction_timing(
            "start.base_drag_layout",
            started_at=phase_started_at,
            gesture_id=gesture_id,
            event_id=event_id,
            row_count=len(self._base_drag_layout_view.rows),
            gap_count=len(self._base_drag_layout_view.gaps),
        )
        self._preview_layout_view = None
        self._clear_preview_target_identity()
        self._gesture.set_active_drop_target(None)
        self._placement_snapshot = None
        self._active_placement = None
        self._landing_shadow.reset_drag_state()
        self._clear_last_drop_commit_context()
        phase_started_at = reorder_drag_started_at()
        self._capture_drag_intent_context(chip, global_pos=press_global_pos)
        self._capture_held_shadow_geometry(chip)
        self._ensure_drag_proxy_render_state()
        self._log_interaction_timing(
            "start.capture_intent",
            started_at=phase_started_at,
            gesture_id=gesture_id,
            event_id=event_id,
            drag_grab_offset_x=(
                "none"
                if self._gesture.state.drag_grab_offset is None
                else f"{self._gesture.state.drag_grab_offset.x():.2f}"
            ),
            drag_grab_offset_y=(
                "none"
                if self._gesture.state.drag_grab_offset is None
                else f"{self._gesture.state.drag_grab_offset.y():.2f}"
            ),
            drag_intent_width=(
                "none"
                if self._gesture.state.drag_intent_size is None
                else f"{self._gesture.state.drag_intent_size.width():.2f}"
            ),
            drag_intent_height=(
                "none"
                if self._gesture.state.drag_intent_size is None
                else f"{self._gesture.state.drag_intent_size.height():.2f}"
            ),
        )
        self._update_preview_layout()
        self._emit_preview_layout_changed()
        self._update_drop_target_from_global_position(global_pos)
        self._update_chip_geometry()
        self._drag_proxy.show()
        self._move_drag_proxy(global_pos)
        self._update_chip_states()
        self._sync_reorder_view_state(reason="drag_started")
        self._log_interaction_timing(
            "start.total",
            started_at=total_started_at,
            gesture_id=gesture_id,
            event_id=event_id,
            active_target_kind=reorder_drag_target_kind(
                self._gesture.state.active_drop_target
            ),
            lane_count=len(self._drop_target_lanes),
            visual_target_count=len(self._drop_target_visuals),
        )

    def drag_move(self, chip: _SegmentChip, global_pos: QPoint) -> None:
        """Update insertion preview while the user drags one segment."""

        if self._gesture.state.dragged_segment_index != chip.segment_index:
            return
        self._emit_drag_intent(
            PromptReorderDragIntent(
                phase="move",
                segment_index=chip.segment_index,
                global_position=global_pos,
            )
        )
        total_started_at = reorder_drag_started_at()
        event_id = self._begin_instrumented_drag_event()
        work_unit_id = self.next_instrumentation_work_unit_id()
        self._instrumentation_drag_move_count += 1
        previous_target = self._gesture.state.active_drop_target
        self._gesture.update_pointer_drag_position(global_pos)
        self._pointer_loop_depth += 1
        pre_target_sample = self._telemetry.should_log_pointer_event(
            move_count=self._instrumentation_drag_move_count,
            target_changed=False,
        )
        if pre_target_sample:
            self._log_interaction_event(
                "pointer_loop.begin",
                gesture_id=self._instrumentation_gesture_id,
                event_id=event_id,
                work_unit_id=work_unit_id,
                move_count=self._instrumentation_drag_move_count,
                dragged_segment_index=chip.segment_index,
            )
        try:
            phase_started_at = reorder_drag_started_at()
            proxy_elapsed_ms = self._move_drag_proxy(
                global_pos,
                log_timing=pre_target_sample,
            )
            if pre_target_sample:
                self._log_interaction_timing(
                    "drag_move.proxy",
                    started_at=phase_started_at,
                    gesture_id=self._instrumentation_gesture_id,
                    event_id=event_id,
                    work_unit_id=work_unit_id,
                    move_count=self._instrumentation_drag_move_count,
                )
            phase_started_at = reorder_drag_started_at()
            self._update_drop_target_from_global_position(global_pos)
            target_changed = previous_target != self._gesture.state.active_drop_target
            pointer_sample = self._telemetry.should_log_pointer_event(
                move_count=self._instrumentation_drag_move_count,
                target_changed=target_changed,
            )
            if pointer_sample:
                target_elapsed_ms = self._log_interaction_timing(
                    "drag_move.target_update",
                    started_at=phase_started_at,
                    gesture_id=self._instrumentation_gesture_id,
                    event_id=event_id,
                    work_unit_id=work_unit_id,
                    move_count=self._instrumentation_drag_move_count,
                    previous_target_kind=reorder_drag_target_kind(previous_target),
                    active_target_kind=reorder_drag_target_kind(
                        self._gesture.state.active_drop_target
                    ),
                    target_changed=target_changed,
                )
            else:
                target_elapsed_ms = (time.perf_counter() - phase_started_at) * 1000.0
            phase_started_at = reorder_drag_started_at()
            self._autoscroll.update_for_pointer(global_pos)
            if pointer_sample:
                autoscroll_elapsed_ms = self._log_interaction_timing(
                    "drag_move.autoscroll",
                    started_at=phase_started_at,
                    gesture_id=self._instrumentation_gesture_id,
                    event_id=event_id,
                    work_unit_id=work_unit_id,
                    move_count=self._instrumentation_drag_move_count,
                    autoscroll_direction=self._autoscroll.direction,
                )
            else:
                autoscroll_elapsed_ms = (
                    time.perf_counter() - phase_started_at
                ) * 1000.0
        finally:
            self._pointer_loop_depth -= 1
        if pointer_sample:
            drag_elapsed_ms = self._log_interaction_timing(
                "drag_move.total",
                started_at=total_started_at,
                gesture_id=self._instrumentation_gesture_id,
                event_id=event_id,
                work_unit_id=work_unit_id,
                move_count=self._instrumentation_drag_move_count,
                dragged_segment_index=chip.segment_index,
                active_target_kind=reorder_drag_target_kind(
                    self._gesture.state.active_drop_target
                ),
                target_changed=target_changed,
                lane_count=len(self._drop_target_lanes),
                visual_target_count=len(self._drop_target_visuals),
                proxy_elapsed_ms=f"{proxy_elapsed_ms:.3f}",
                target_elapsed_ms=f"{target_elapsed_ms:.3f}",
                autoscroll_elapsed_ms=f"{autoscroll_elapsed_ms:.3f}",
            )
            self._log_interaction_event(
                "pointer_loop.allowed_work",
                gesture_id=self._instrumentation_gesture_id,
                event_id=event_id,
                work_unit_id=work_unit_id,
                proxy_elapsed_ms=f"{proxy_elapsed_ms:.3f}",
                target_elapsed_ms=f"{target_elapsed_ms:.3f}",
                autoscroll_elapsed_ms=f"{autoscroll_elapsed_ms:.3f}",
            )
            self._log_interaction_event(
                "pointer_loop.end",
                gesture_id=self._instrumentation_gesture_id,
                event_id=event_id,
                work_unit_id=work_unit_id,
                elapsed_ms=f"{drag_elapsed_ms:.3f}",
            )
        else:
            drag_elapsed_ms = (time.perf_counter() - total_started_at) * 1000.0
        self._instrumentation_max_drag_move_ms = max(
            self._instrumentation_max_drag_move_ms,
            drag_elapsed_ms,
        )
        if target_changed:
            self._instrumentation_target_change_count += 1
        self._log_slow_path_if_needed(
            "slow.drag_move",
            elapsed_ms=drag_elapsed_ms,
            threshold_ms=_SLOW_DRAG_MOVE_MS,
            move_count=self._instrumentation_drag_move_count,
            target_changed=target_changed,
            active_target_kind=reorder_drag_target_kind(
                self._gesture.state.active_drop_target
            ),
        )

    def end_drag(self, chip: _SegmentChip) -> None:
        """Finish the current drag while preserving the reordered index state."""

        if self._gesture.state.dragged_segment_index != chip.segment_index:
            return
        last_drag_global_position = self._gesture.state.last_drag_global_position
        self._emit_drag_intent(
            PromptReorderDragIntent(
                phase="end",
                segment_index=chip.segment_index,
                global_position=last_drag_global_position or QPoint(),
            )
        )
        total_started_at = reorder_drag_started_at()
        event_id = self._begin_instrumented_drag_event()
        self.flush_pending_autoscroll_invalidation(
            reason="autoscroll_pointer_drop_settle"
        )
        self._settle_chip_animations(reason="pointer_drop")
        ending_target = self._gesture.state.active_drop_target
        self._log_drop_release_snapshot(
            dragged_segment_index=chip.segment_index,
            ending_target=ending_target,
        )
        if (
            self._preview_layout_view is not None
            and self._gesture.state.active_drop_target is not None
            and self._current_layout_view is not None
        ):
            self._current_layout_view = self._preview_layout_view
            self._current_reorder_state = self._preview_reorder_state
            self._geometry.current_layout_view = self._current_layout_view
            self._geometry.current_reorder_state = self._current_reorder_state
            self._ordered_segment_indices = list(
                self._geometry.ordered_indices_for_layout(self._current_layout_view)
            )
            self._geometry.ordered_segment_indices = list(self._ordered_segment_indices)
            self._gesture.set_committed_dragged_segment(chip.segment_index)
            self._last_drop_commit_visual = (
                self._landing_shadow.last_landing_preview_visual
            )
            self._last_drop_commit_geometry = (
                self._landing_shadow.last_landing_preview_geometry
            )
            self._last_drop_commit_target = ending_target
            self._last_drop_commit_placement = self._active_placement
            self._last_drop_commit_segment_index = chip.segment_index
            self._last_drop_commit_gesture_id = self._instrumentation_gesture_id
            self._last_drop_commit_event_id = event_id
        else:
            self._gesture.set_active_drop_target(None)
            self._active_placement = None
            self._preview_layout_view = None
            self._clear_preview_target_identity()
            self._clear_last_drop_commit_context()
            if self._current_layout_view is not None:
                self._ordered_segment_indices = list(
                    self._geometry.ordered_indices_for_layout(self._current_layout_view)
                )
                self._geometry.ordered_segment_indices = list(
                    self._ordered_segment_indices
                )
        self._gesture.finish_pointer_drag(
            committed_segment_index=None,
            clear_target=False,
        )
        self._landing_shadow.reset_drag_state()
        self._clear_drag_intent_context()
        self._clear_base_drag_context()
        self._clear_preview_target_identity()
        self._drag_proxy.hide()
        self._autoscroll.stop()
        self._clear_pending_autoscroll_invalidation()
        self._update_preview_layout()
        self._update_chip_geometry()
        self._log_post_drop_geometry_checkpoint(
            checkpoint="end_drag.after_geometry_update",
            segment_index=chip.segment_index,
        )
        self._update_chip_states()
        self._sync_reorder_view_state(reason="drag_ended")
        self._emit_preview_layout_changed()
        self._emit_commit_intent(
            PromptReorderCommitIntent(
                reason="pointer_drop",
                snapshot=self.commit_snapshot(),
            )
        )
        self._log_interaction_timing(
            "end.total",
            started_at=total_started_at,
            gesture_id=self._instrumentation_gesture_id,
            event_id=event_id,
            dragged_segment_index=chip.segment_index,
            committed_target_kind=reorder_drag_target_kind(ending_target),
            has_reordered=self.has_reordered(),
            ordered_count=len(self._ordered_segment_indices),
            move_count=self._instrumentation_drag_move_count,
        )
        self._log_gesture_summary(outcome="end")
        self._instrumentation_gesture_id = None
        self._instrumentation_event_id = None

    def cancel_drag(self) -> None:
        """Clear drag visuals without mutating the underlying text."""

        total_started_at = reorder_drag_started_at()
        event_id = self._begin_instrumented_drag_event()
        self._settle_chip_animations(reason="drag_cancelled")
        self._gesture.cancel_drag()
        self._placement_snapshot = None
        self._active_placement = None
        self._landing_shadow.reset_drag_state()
        self._clear_drag_intent_context()
        self._clear_base_drag_context()
        self._preview_layout_view = None
        self._clear_preview_target_identity()
        self._current_layout_view = self._original_layout_view
        self._current_reorder_state = self._original_reorder_state
        self._geometry.current_layout_view = self._current_layout_view
        self._geometry.current_reorder_state = self._current_reorder_state
        self._geometry.preview_layout_view = None
        self._geometry.preview_reorder_state = None
        self._ordered_segment_indices = list(self._initial_ordered_indices)
        self._geometry.ordered_segment_indices = list(self._ordered_segment_indices)
        self._drag_proxy.hide()
        self._autoscroll.stop()
        self._clear_pending_autoscroll_invalidation()
        self._update_preview_layout()
        self._update_chip_geometry()
        self._update_chip_states()
        self._sync_reorder_view_state(reason="drag_cancelled")
        self._emit_preview_layout_changed()
        self._log_interaction_timing(
            "cancel.total",
            started_at=total_started_at,
            gesture_id=self._instrumentation_gesture_id,
            event_id=event_id,
            move_count=self._instrumentation_drag_move_count,
        )
        self._log_gesture_summary(outcome="cancel")
        self._instrumentation_gesture_id = None
        self._instrumentation_event_id = None
        self._clear_last_drop_commit_context()

    def _emit_drag_intent(self, intent: PromptReorderDragIntent) -> None:
        """Publish one drag intent to the interaction owner when connected."""

        if self._drag_handler is not None:
            self._drag_handler(intent)

    def _emit_commit_intent(self, intent: PromptReorderCommitIntent) -> None:
        """Publish one commit intent to the interaction owner when connected."""

        if self._commit_handler is not None:
            self._commit_handler(intent)

    def _emit_cancel_intent(self, intent: PromptReorderCancelIntent) -> None:
        """Publish one cancel intent to the interaction owner when connected."""

        if self._cancel_handler is not None:
            self._cancel_handler(intent)

    def _move_active_chip_by_keyboard(
        self,
        *,
        horizontal_step: int | None = None,
        vertical_direction: int | None = None,
    ) -> bool:
        """Delegate one keyboard move to projection-owned navigation."""

        if not self._prepare_keyboard_navigation_context():
            return False

        if horizontal_step is not None:
            result = self._geometry.move_keyboard_horizontally(
                active_segment_index=self._gesture.state.base_drag_segment_index,
                active_target=self._gesture.state.active_drop_target,
                preferred_x=self._gesture.state.keyboard_preferred_x,
                step=horizontal_step,
                gesture_id=self._instrumentation_gesture_id,
                event_id=self._instrumentation_event_id,
            )
        else:
            assert vertical_direction is not None
            result = self._geometry.move_keyboard_vertically(
                active_segment_index=self._gesture.state.base_drag_segment_index,
                active_target=self._gesture.state.active_drop_target,
                direction=vertical_direction,
                preferred_x=self._gesture.state.keyboard_preferred_x,
                gesture_id=self._instrumentation_gesture_id,
                event_id=self._instrumentation_event_id,
            )
        if not result.moved:
            return False
        held_segment_index = self._gesture.state.base_drag_segment_index
        if held_segment_index is None:
            return False
        self._mark_reorder_displacement_target_changed(
            ReorderDisplacementIntent(
                source="keyboard",
                held_segment_index=held_segment_index,
                target=result.destination_target,
                pointer_global_pos=None,
                reason="keyboard_target_changed",
            )
        )
        self._sync_keyboard_navigation_result(
            target=result.destination_target,
            preferred_x=result.preferred_x,
        )
        return True

    def _prepare_keyboard_navigation_context(self) -> bool:
        """Prepare stable projection geometry for delegated keyboard navigation."""

        if self._gesture.state.dragged_segment_index is not None:
            return False

        active_segment_index = self._gesture.state.active_segment_index
        current_layout_view = self._current_layout_view
        document_view = self._document_view
        if (
            active_segment_index is None
            or current_layout_view is None
            or document_view is None
        ):
            return False

        if (
            self._gesture.state.base_drag_segment_index == active_segment_index
            and self._base_drag_layout_view is not None
            and self._drop_target_lanes
        ):
            return True

        self._gesture.set_base_drag_segment(active_segment_index)
        self._base_drag_layout_view = self._geometry.begin_drag(
            dragged_segment_index=active_segment_index,
            gesture_id=self._instrumentation_gesture_id,
            event_id=self._instrumentation_event_id,
        )
        self._base_drag_reorder_state = self._geometry.base_drag_reorder_state
        self._emit_preview_layout_changed()
        return bool(self._drop_target_lanes)

    def _committable_keyboard_drop_target(self) -> PromptReorderDropTarget | None:
        """Return the active chip's current insertion target relative to base-drag state."""

        if self._gesture.state.active_drop_target is not None:
            return self._gesture.state.active_drop_target
        return self._projection_drop_target_for_visible_order()

    def _projection_drop_target_for_visible_order(
        self,
    ) -> PromptReorderDropTarget | None:
        """Resolve the target whose preview layout matches the current visible order."""

        active_segment_index = self._gesture.state.base_drag_segment_index
        current_layout_view = self._current_layout_view
        document_view = self._document_view
        if (
            active_segment_index is None
            or current_layout_view is None
            or document_view is None
        ):
            return None

        _ = document_view
        _ = current_layout_view
        return self._geometry.resolve_drop_target_for_current_layout(
            active_segment_index=active_segment_index
        )

    def _sync_keyboard_navigation_result(
        self,
        *,
        target: PromptReorderDropTarget,
        preferred_x: float | None,
    ) -> None:
        """Publish projection-owned keyboard movement back to overlay visual state."""

        self._current_layout_view = self._geometry.current_layout_view
        self._current_reorder_state = self._geometry.current_reorder_state
        self._preview_layout_view = None
        self._preview_reorder_state = None
        self._ordered_segment_indices = list(self._geometry.ordered_segment_indices)
        self._base_drag_layout_view = self._geometry.base_drag_layout_view
        self._base_drag_reorder_state = self._geometry.base_drag_reorder_state
        self._gesture.set_active_drop_target(target)
        self._gesture.set_keyboard_preferred_x(preferred_x)
        self._update_chip_states()
        self._emit_preview_layout_changed()

    def _clear_base_drag_context(self) -> None:
        """Clear any stable base-drag geometry and keyboard navigation intent."""

        self._gesture.clear_base_drag_segment()
        self._geometry.clear_drag_context()
        self._base_drag_layout_view = None
        self._base_drag_reorder_state = None
        self._base_drag_chip_geometry_snapshot = None
        self._base_drag_visuals_by_index = {}
        self._landing_shadow.clear_held_shadow()
        self._gesture.clear_keyboard_preferred_x()

    def _begin_instrumented_drag_event(self) -> int:
        """Advance and return the current drag event identifier."""

        self._instrumentation_next_event_id += 1
        self._instrumentation_event_id = self._instrumentation_next_event_id
        return self._instrumentation_next_event_id

    def log_interaction_event(self, event: str, **context: object) -> None:
        """Log interaction telemetry without letting validation abort gestures."""

        self._log_interaction_event(event, **context)

    def _log_interaction_event(self, event: str, **context: object) -> None:
        """Delegate prompt-safe event logging to the telemetry owner."""

        self._telemetry.log_event(event, **context)

    def _log_interaction_timing(
        self,
        event: str,
        *,
        started_at: float,
        **context: object,
    ) -> float:
        """Delegate prompt-safe timing logging to the telemetry owner."""

        return self._telemetry.log_timing(event, started_at=started_at, **context)

    def _log_slow_path_if_needed(
        self,
        event: str,
        *,
        elapsed_ms: float,
        threshold_ms: float,
        **context: object,
    ) -> None:
        """Emit one slow-path diagnostic when an operation exceeds its frame budget."""

        self._telemetry.log_slow_path_if_needed(
            event,
            elapsed_ms=elapsed_ms,
            threshold_ms=threshold_ms,
            gesture_id=self._instrumentation_gesture_id,
            event_id=self._instrumentation_event_id,
            **context,
        )

    def _log_reorder_anomaly(self, event: str, **context: object) -> None:
        """Emit and count one visual or placement anomaly for gesture summaries."""

        self._instrumentation_anomaly_count += 1
        self._log_interaction_event(
            event,
            gesture_id=self._instrumentation_gesture_id,
            event_id=self._instrumentation_event_id,
            **context,
        )

    def _log_expected_geometry_diagnostic(
        self,
        event: str,
        **context: object,
    ) -> None:
        """Emit a non-anomaly diagnostic for expected geometry offsets."""

        self._instrumentation_expected_diagnostic_count += 1
        self._log_interaction_event(
            event,
            gesture_id=self._instrumentation_gesture_id,
            event_id=self._instrumentation_event_id,
            **context,
        )

    def _log_gesture_summary(self, *, outcome: str) -> None:
        """Emit one compact end-of-gesture summary for repro log review."""

        chip_geometry_count = (
            0
            if self._chip_geometry_snapshot is None
            else len(self._chip_geometry_snapshot.geometries_by_chip_index)
        )
        expected_chip_count = len(self._segments_by_index)
        chip_geometry_missing_count = max(0, expected_chip_count - chip_geometry_count)
        preview_chip_geometry_count = (
            0
            if self._preview_chip_geometry_snapshot is None
            else len(self._preview_chip_geometry_snapshot.geometries_by_chip_index)
        )
        placement_geometry_count = (
            0
            if self._placement_snapshot is None
            else len(self._placement_snapshot.placements)
        )
        cache_counters = self._owner_performance_counters()
        self._log_interaction_event(
            "gesture_summary",
            gesture_id=self._instrumentation_gesture_id,
            event_id=self._instrumentation_event_id,
            outcome=outcome,
            move_count=self._instrumentation_drag_move_count,
            target_change_count=self._instrumentation_target_change_count,
            placement_change_count=self._instrumentation_target_change_count,
            drop_target_no_change_count=(
                self._instrumentation_drop_target_no_change_count
            ),
            drop_target_changed_count=self._instrumentation_drop_target_changed_count,
            preview_sync_immediate_count=(
                self._instrumentation_preview_sync_immediate_count
            ),
            preview_sync_deferred_count=self._instrumentation_preview_sync_deferred_count,
            pointer_unexpected_work_count=(
                self._instrumentation_pointer_unexpected_work_count
            ),
            pointer_preview_rebuild_count=(
                self._instrumentation_pointer_preview_rebuild_count
            ),
            pointer_full_refresh_count=(
                self._instrumentation_pointer_full_refresh_count
            ),
            pointer_base_cache_miss_count=(
                self._instrumentation_pointer_base_cache_miss_count
            ),
            pointer_paint_request_count=(
                self._instrumentation_pointer_paint_request_count
            ),
            refresh_work_unit_count=self._instrumentation_refresh_work_unit_count,
            skipped_refresh_count=self._instrumentation_skipped_refresh_count,
            overlay_position_skip_count=(
                self._instrumentation_position_refresh_skip_count
            ),
            overlay_position_run_count=self._instrumentation_position_refresh_run_count,
            preview_scheduler_request_count=(
                self._instrumentation_preview_scheduler_request_count
            ),
            preview_scheduler_run_count=(
                self._instrumentation_preview_scheduler_run_count
            ),
            preview_scheduler_stale_skip_count=(
                self._instrumentation_preview_scheduler_stale_skip_count
            ),
            preview_geometry_suppressed_count=(
                self._instrumentation_preview_geometry_suppressed_count
            ),
            preview_geometry_full_count=self._instrumentation_preview_geometry_full_count,
            initial_shadow_sync_count=(
                self._landing_shadow.counters.initial_shadow_sync_count
            ),
            initial_shadow_ready_count=(
                self._landing_shadow.counters.initial_shadow_ready_count
            ),
            stale_shadow_rejected_count=(
                self._landing_shadow.counters.stale_shadow_rejected_count
            ),
            base_drag_geometry_reuse_count=(
                self._instrumentation_base_drag_geometry_reuse_count
            ),
            base_drag_geometry_rebuild_count=(
                self._instrumentation_base_drag_geometry_rebuild_count
            ),
            preview_geometry_reused_chip_count=(
                self._instrumentation_preview_geometry_reused_chip_count
            ),
            preview_geometry_rebuilt_chip_count=(
                self._instrumentation_preview_geometry_rebuilt_chip_count
            ),
            preview_geometry_reuse_rejected_count=(
                self._instrumentation_preview_geometry_reuse_rejected_count
            ),
            held_shadow_capture_count=(
                self._landing_shadow.counters.held_shadow_capture_count
            ),
            held_shadow_missing_count=(
                self._landing_shadow.counters.held_shadow_missing_count
            ),
            pending_shadow_fallback_count=(
                self._landing_shadow.counters.pending_shadow_fallback_count
            ),
            pending_shadow_replaced_marker_count=(
                self._landing_shadow.counters.pending_shadow_replaced_marker_count
            ),
            marker_fallback_count=self._instrumentation_marker_fallback_count,
            diagnostic_expected_offset_count=(
                self._instrumentation_expected_diagnostic_count
                + self._landing_shadow.counters.expected_diagnostic_count
            ),
            no_lane_count=self._instrumentation_no_lane_count,
            anomaly_count=(
                self._instrumentation_anomaly_count
                + self._landing_shadow.counters.anomaly_count
            ),
            split_shadow_count=self._instrumentation_split_shadow_count,
            chip_geometry_count=chip_geometry_count,
            preview_chip_geometry_count=preview_chip_geometry_count,
            expected_chip_count=expected_chip_count,
            chip_geometry_missing_count=chip_geometry_missing_count,
            chip_geometry_duplicate_count=0,
            chip_geometry_mismatch_count=0,
            placement_geometry_count=placement_geometry_count,
            max_drag_move_ms=f"{self._instrumentation_max_drag_move_ms:.3f}",
            max_preview_sync_ms=f"{self._instrumentation_max_preview_sync_ms:.3f}",
            max_live_visuals_ms=f"{self._instrumentation_max_live_visuals_ms:.3f}",
            max_render_plan_ms=f"{self._instrumentation_max_render_plan_ms:.3f}",
            **cache_counters,
        )

    def _owner_performance_counters(self) -> dict[str, object]:
        """Return counters owned by surface, drag proxy, and autoscroll collaborators."""

        return {
            **self._editor.reorder_geometry_cache_counters(),
            **self._drag_proxy_state_factory.counters(),
            **self._autoscroll.counters(),
            **self._animation_presenter.counters(),
            **self._held_chip_presenter.counters().as_dict(),
            **self._raster_cache.counters().as_dict(),
            "animation_plan_build_count": self._instrumentation_animation_plan_build_count,
            "landing_paint_cache_hit_count": (
                self._landing_shadow.counters.paint_cache_hit_count
            ),
            "landing_paint_cache_miss_count": (
                self._landing_shadow.counters.paint_cache_miss_count
            ),
        }

    def reorder_performance_counters(self) -> dict[str, object]:
        """Return deterministic Phase 1 reorder performance counters."""

        return {
            "drag_move_count": self._instrumentation_drag_move_count,
            "target_change_count": self._instrumentation_target_change_count,
            "drop_target_no_change_count": (
                self._instrumentation_drop_target_no_change_count
            ),
            "drop_target_changed_count": (
                self._instrumentation_drop_target_changed_count
            ),
            "preview_geometry_full_count": (
                self._instrumentation_preview_geometry_full_count
            ),
            "pointer_unexpected_work_count": (
                self._instrumentation_pointer_unexpected_work_count
            ),
            "pointer_preview_rebuild_count": (
                self._instrumentation_pointer_preview_rebuild_count
            ),
            "pointer_full_refresh_count": (
                self._instrumentation_pointer_full_refresh_count
            ),
            "pointer_base_cache_miss_count": (
                self._instrumentation_pointer_base_cache_miss_count
            ),
            "pointer_paint_request_count": (
                self._instrumentation_pointer_paint_request_count
            ),
            "preview_scheduler_request_count": (
                self._instrumentation_preview_scheduler_request_count
            ),
            "preview_scheduler_run_count": (
                self._instrumentation_preview_scheduler_run_count
            ),
            "autoscroll_schedule_count": (
                self._instrumentation_autoscroll_schedule_count
            ),
            "autoscroll_coalesced_count": (
                self._instrumentation_autoscroll_coalesced_count
            ),
            "autoscroll_flush_count": (self._instrumentation_autoscroll_flush_count),
            "autoscroll_target_refresh_count": (
                self._instrumentation_autoscroll_target_refresh_count
            ),
            "autoscroll_pending_invalidation_count": int(
                self._pending_autoscroll_invalidation is not None
            ),
            "max_drag_move_ms": self._instrumentation_max_drag_move_ms,
            "max_preview_sync_ms": self._instrumentation_max_preview_sync_ms,
            "max_live_visuals_ms": self._instrumentation_max_live_visuals_ms,
            "max_render_plan_ms": self._instrumentation_max_render_plan_ms,
            "raster_entries_render_cache_hit_count": (
                self._instrumentation_raster_entries_render_cache_hit_count
            ),
            "raster_entries_render_cache_miss_count": (
                self._instrumentation_raster_entries_render_cache_miss_count
            ),
            **self._owner_performance_counters(),
        }

    def record_preview_sync_elapsed(self, elapsed_ms: float) -> None:
        """Record controller preview-sync timing for the active gesture summary."""

        self._instrumentation_max_preview_sync_ms = max(
            self._instrumentation_max_preview_sync_ms,
            elapsed_ms,
        )

    def record_preview_sync_decision(self, *, immediate: bool) -> None:
        """Record controller preview-sync scheduling decisions for diagnostics."""

        if immediate:
            self._instrumentation_preview_sync_immediate_count += 1
            return
        self._instrumentation_preview_sync_deferred_count += 1

    def is_drag_pointer_loop_active(self) -> bool:
        """Return whether a drag pointer event is currently being processed."""

        return self._pointer_loop_depth > 0

    def next_instrumentation_work_unit_id(self) -> int:
        """Return the next per-gesture work-unit id for correlated diagnostics."""

        self._instrumentation_work_unit_id += 1
        return self._instrumentation_work_unit_id

    def current_instrumentation_work_unit_id(self) -> int:
        """Return the latest per-gesture work-unit id without incrementing it."""

        return self._instrumentation_work_unit_id

    def record_preview_scheduler_event(self, event: str) -> None:
        """Record scheduler work classifications for gesture summaries."""

        if event == "requested":
            self._instrumentation_preview_scheduler_request_count += 1
        elif event == "ran_latest":
            self._instrumentation_preview_scheduler_run_count += 1
        elif event == "skipped_stale":
            self._instrumentation_preview_scheduler_stale_skip_count += 1

    def record_pointer_unexpected_work(self, work: str, **context: object) -> None:
        """Log expensive work that ran during the protected pointer loop."""

        if self._pointer_loop_depth <= 0:
            return
        self._instrumentation_pointer_unexpected_work_count += 1
        if work == "preview_rebuild":
            self._instrumentation_pointer_preview_rebuild_count += 1
        elif work == "full_refresh":
            self._instrumentation_pointer_full_refresh_count += 1
        elif work == "base_cache_miss":
            self._instrumentation_pointer_base_cache_miss_count += 1
        elif work == "paint_request":
            self._instrumentation_pointer_paint_request_count += 1
        self._log_interaction_event(
            "pointer_loop.unexpected_work",
            gesture_id=self._instrumentation_gesture_id,
            event_id=self._instrumentation_event_id,
            work=work,
            **context,
        )

    def record_render_plan_elapsed(self, elapsed_ms: float) -> None:
        """Record controller render-plan timing for the active gesture summary."""

        self._instrumentation_max_render_plan_ms = max(
            self._instrumentation_max_render_plan_ms,
            elapsed_ms,
        )

    def _cancel_chip_animations(self, *, reason: str) -> None:
        """Stop active chip animation without applying target geometry."""

        self._animation_presenter.cancel(reason=reason)
        self._held_chip_presenter.cancel(reason=reason)

    def _settle_chip_animations(self, *, reason: str) -> None:
        """Place animated chip widgets at their latest presenter targets."""

        self._animation_presenter.settle(reason=reason)
        self._held_chip_presenter.settle(reason=reason)

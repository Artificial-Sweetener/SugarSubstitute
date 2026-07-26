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

"""Own prompt reorder preview sync scheduling and stale-work rejection."""

from __future__ import annotations

from collections.abc import Callable

from substitute.application.prompt_editor.reorder.preview_sync import (
    PromptReorderPreviewFlushDecision,
    PromptReorderPreviewScheduleMode,
    PromptReorderPreviewSyncContext,
    PromptReorderPreviewSyncPolicy,
    PromptReorderPreviewSyncState,
)

from ..projection.observability import (
    log_reorder_drag_event,
    log_reorder_drag_timing,
    reorder_drag_started_at,
)
from .reorder_preview_timer import (
    PromptReorderPreviewTimer,
    PromptReorderPreviewTimerFactory,
)

_SLOW_PREVIEW_SYNC_MS = 8.0


class PromptReorderPreviewSyncController:
    """Own pending preview sync bookkeeping and coalescing decisions."""

    def __init__(
        self,
        *,
        interval_ms: int,
        run_sync: Callable[[], None],
        pointer_revision: Callable[[], int | None] | None = None,
        record_scheduler_event: Callable[[str], None] | None = None,
        timer_factory: PromptReorderPreviewTimerFactory | None = None,
    ) -> None:
        """Initialize a latest-wins preview sync owner."""

        self._interval_ms = interval_ms
        self._run_sync = run_sync
        self._pending_record_elapsed: Callable[[float], None] | None = None
        self._policy = PromptReorderPreviewSyncPolicy()
        self._timer = PromptReorderPreviewTimer(
            interval_ms=interval_ms,
            run_pending=self.flush_pending,
            timer_factory=timer_factory,
            pointer_revision=pointer_revision,
            record_event=record_scheduler_event,
        )

    @property
    def active_reason(self) -> str | None:
        """Return the reason attached to the sync currently being applied."""

        return self._policy.active_reason

    @property
    def state(self) -> PromptReorderPreviewSyncState:
        """Return immutable preview-sync bookkeeping for tests."""

        return self._policy.snapshot(
            scheduler_active=self._timer.is_active(),
        )

    def has_pending(self) -> bool:
        """Return whether a preview sync request is waiting to run."""

        return self._policy.pending_revision is not None

    def schedule(
        self,
        *,
        reason: str,
        context: PromptReorderPreviewSyncContext,
        record_decision: Callable[[bool], None],
        record_elapsed: Callable[[float], None] | None = None,
    ) -> None:
        """Record and schedule the latest preview sync request."""

        started_at = reorder_drag_started_at()
        self._pending_record_elapsed = record_elapsed
        schedule_mode = self._policy.request(reason=reason, context=context)
        revision = self._policy.current_revision
        if schedule_mode is PromptReorderPreviewScheduleMode.IMMEDIATE:
            record_decision(True)
            log_reorder_drag_event(
                "preview_sync.immediate_base_geometry_missing",
                gesture_id=context.gesture_id,
                event_id=context.event_id,
                reason=reason,
                revision=revision,
            )
            log_reorder_drag_timing(
                "interaction.schedule_preview_sync.immediate",
                started_at=started_at,
                gesture_id=context.gesture_id,
                event_id=context.event_id,
                reason=reason,
                revision=revision,
                dragged_segment_index=context.dragged_segment_index,
            )
            self.flush_pending(reason="drag_reorder_prepare", forced=True)
            return
        record_decision(False)
        self._timer.request(
            revision=revision,
            reason=reason,
            pointer_active=context.pointer_active,
            gesture_id=context.gesture_id,
            event_id=context.event_id,
        )
        if context.dragged_segment_index is not None and context.base_drag_layout_ready:
            log_reorder_drag_event(
                "preview_sync.deferred_base_geometry_ready",
                gesture_id=context.gesture_id,
                event_id=context.event_id,
                reason=reason,
                revision=revision,
            )
        log_reorder_drag_timing(
            "interaction.schedule_preview_sync.deferred",
            started_at=started_at,
            gesture_id=context.gesture_id,
            event_id=context.event_id,
            reason=reason,
            revision=revision,
            timer_active=self._timer.is_active(),
            interval_ms=self._interval_ms,
        )

    def flush_pending(
        self,
        *,
        reason: str | None = None,
        forced: bool = False,
        context: PromptReorderPreviewSyncContext | None = None,
        record_elapsed: Callable[[float], None] | None = None,
    ) -> None:
        """Apply the latest pending sync unless it is stale."""

        started_at = reorder_drag_started_at()
        gesture_id = None if context is None else context.gesture_id
        event_id = None if context is None else context.event_id
        decision = self._policy.begin_flush(context=context)
        pending_revision = self._policy.flush_revision
        if decision is PromptReorderPreviewFlushDecision.NO_PENDING:
            log_reorder_drag_timing(
                "interaction.flush_preview_sync.noop",
                started_at=started_at,
                gesture_id=gesture_id,
                event_id=event_id,
                reason=reason,
                forced=forced,
            )
            return
        pending_reason = self._policy.flush_reason
        pending_context = self._policy.flush_context
        pending_record_elapsed = record_elapsed or self._pending_record_elapsed
        self._pending_record_elapsed = None
        gesture_id = None if pending_context is None else pending_context.gesture_id
        event_id = None if pending_context is None else pending_context.event_id
        if self._timer.is_active():
            self._timer.stop()
        if decision is PromptReorderPreviewFlushDecision.STALE:
            log_reorder_drag_event(
                "preview_scheduler.skipped_stale",
                gesture_id=gesture_id,
                event_id=event_id,
                reason=reason,
                pending_reason=pending_reason,
                pending_revision=pending_revision,
                last_applied_revision=self._policy.last_applied_revision,
            )
            log_reorder_drag_timing(
                "interaction.flush_preview_sync.stale",
                started_at=started_at,
                gesture_id=gesture_id,
                event_id=event_id,
                reason=reason,
                pending_reason=pending_reason,
                forced=forced,
                pending_revision=pending_revision,
                last_applied_revision=self._policy.last_applied_revision,
            )
            return
        published = False
        try:
            self._run_sync()
            published = True
        finally:
            self._policy.complete_flush(published=published)
        preview_sync_elapsed_ms = log_reorder_drag_timing(
            "interaction.flush_preview_sync.total",
            started_at=started_at,
            gesture_id=gesture_id,
            event_id=event_id,
            reason=reason,
            pending_reason=pending_reason,
            forced=forced,
            pending_revision=pending_revision,
            last_applied_revision=self._policy.last_applied_revision,
        )
        if pending_record_elapsed is not None:
            pending_record_elapsed(preview_sync_elapsed_ms)
        if preview_sync_elapsed_ms >= _SLOW_PREVIEW_SYNC_MS:
            log_reorder_drag_event(
                "slow.preview_sync",
                gesture_id=gesture_id,
                event_id=event_id,
                elapsed_ms=f"{preview_sync_elapsed_ms:.3f}",
                threshold_ms=f"{_SLOW_PREVIEW_SYNC_MS:.3f}",
                reason=reason,
                pending_reason=pending_reason,
                forced=forced,
            )
            log_reorder_drag_event(
                "budget.preview_sync_exceeded",
                gesture_id=gesture_id,
                event_id=event_id,
                elapsed_ms=f"{preview_sync_elapsed_ms:.3f}",
                threshold_ms=f"{_SLOW_PREVIEW_SYNC_MS:.3f}",
                reason=reason,
                pending_reason=pending_reason,
                forced=forced,
            )
            if reason == "initial_shadow_missing":
                log_reorder_drag_event(
                    "budget.initial_shadow_sync_exceeded",
                    gesture_id=gesture_id,
                    event_id=event_id,
                    elapsed_ms=f"{preview_sync_elapsed_ms:.3f}",
                    threshold_ms=f"{_SLOW_PREVIEW_SYNC_MS:.3f}",
                    pending_reason=pending_reason,
                    forced=forced,
                )

    def clear(self) -> None:
        """Forget pending preview sync state and stop scheduled work."""

        self._policy.clear()
        self._pending_record_elapsed = None
        if self._timer.is_active():
            self._timer.stop()

    def replace_state(
        self,
        *,
        pending_revision: int | None = None,
        pending_reason: str | None = None,
        last_applied_revision: int | None = None,
    ) -> None:
        """Replace preview-sync bookkeeping from a prepared scheduler state."""

        self._policy.replace_state(
            pending_revision=pending_revision,
            pending_reason=pending_reason,
            last_applied_revision=last_applied_revision,
        )
        self._pending_record_elapsed = None


__all__ = [
    "PromptReorderPreviewSyncController",
]

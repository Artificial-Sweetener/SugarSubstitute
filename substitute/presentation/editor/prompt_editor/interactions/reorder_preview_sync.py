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
from dataclasses import dataclass
from time import perf_counter
from typing import Protocol, cast

from PySide6.QtCore import QObject, QTimer

from ..projection.observability import (
    log_reorder_drag_event,
    log_reorder_drag_timing,
    reorder_drag_started_at,
)

_POINTER_DEFER_CAP_MS = 96.0
_SLOW_PREVIEW_SYNC_MS = 8.0


class _TimerSignal(Protocol):
    """Describe the timer signal seam used by the preview scheduler."""

    def connect(self, callback: Callable[[], None]) -> object:
        """Connect one timeout callback."""


class _PreviewSchedulerTimer(Protocol):
    """Describe the timer operations required for preview scheduling."""

    timeout: _TimerSignal

    def setSingleShot(self, single_shot: bool) -> None:  # noqa: N802
        """Configure whether the timer fires once."""

    def setInterval(self, interval: int) -> None:  # noqa: N802
        """Configure the default timer interval."""

    def start(self, interval: int) -> None:
        """Start the timer with one explicit interval."""

    def stop(self) -> None:
        """Stop any pending timer tick."""

    def isActive(self) -> bool:  # noqa: N802
        """Return whether the timer is active."""


@dataclass(frozen=True, slots=True)
class PromptReorderPreviewSyncContext:
    """Carry overlay-derived facts needed for one preview sync decision."""

    gesture_id: int | None
    event_id: int | None
    pointer_active: bool
    dragged_segment_index: int | None
    base_drag_layout_ready: bool
    requires_immediate_drag_geometry: bool
    requires_initial_landing_shadow: bool


@dataclass(frozen=True, slots=True)
class PromptReorderPreviewSyncState:
    """Expose preview-sync bookkeeping for focused tests and diagnostics."""

    revision: int
    pending_revision: int | None
    pending_reason: str | None
    active_reason: str | None
    last_applied_revision: int
    scheduler_active: bool


class PromptReorderPreviewScheduler(QObject):
    """Coalesce drag preview projection updates behind pointer feedback."""

    def __init__(
        self,
        *,
        interval_ms: int,
        run_pending: Callable[[], None],
        timer_factory: Callable[[], object] | None = None,
        pointer_revision: Callable[[], int | None] | None = None,
        record_event: Callable[[str], None] | None = None,
        parent: QObject | None = None,
    ) -> None:
        """Initialize the latest-wins timer around one pending-work callback."""

        super().__init__(parent)
        self._interval_ms = interval_ms
        self._run_pending = run_pending
        self._pointer_revision = pointer_revision
        self._record_event = record_event
        self._timer = cast(_PreviewSchedulerTimer, (timer_factory or QTimer)())
        self._timer.setSingleShot(True)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._run)
        self._latest_requested_revision: int | None = None
        self._scheduled_revision: int | None = None
        self._latest_reason: str | None = None
        self._pending_since: float | None = None
        self._latest_request_at: float | None = None
        self._scheduled_pointer_revision: int | None = None
        self._latest_gesture_id: int | None = None
        self._latest_event_id: int | None = None

    def request(
        self,
        *,
        revision: int,
        reason: str,
        pointer_active: bool,
        gesture_id: int | None,
        event_id: int | None,
    ) -> None:
        """Schedule a pending preview sync and log coalescing context."""

        started_at = reorder_drag_started_at()
        now = perf_counter()
        was_active = self._timer.isActive()
        previous_scheduled_revision = self._scheduled_revision
        if self._pending_since is None:
            self._pending_since = now
        self._latest_request_at = now
        self._latest_requested_revision = revision
        self._scheduled_revision = revision
        self._latest_reason = reason
        self._latest_gesture_id = gesture_id
        self._latest_event_id = event_id
        self._scheduled_pointer_revision = self._current_pointer_revision()
        if self._timer.isActive():
            self._timer.stop()
            self._record_scheduler_event("coalesced")
            log_reorder_drag_event(
                "preview_scheduler.coalesced",
                gesture_id=gesture_id,
                event_id=event_id,
                reason=reason,
                revision=revision,
                previous_scheduled_revision=previous_scheduled_revision,
            )
            if (
                previous_scheduled_revision is not None
                and previous_scheduled_revision < revision
            ):
                self._record_scheduler_event("skipped_stale")
                log_reorder_drag_event(
                    "preview_scheduler.skipped_stale",
                    gesture_id=gesture_id,
                    event_id=event_id,
                    reason=reason,
                    skipped_revision=previous_scheduled_revision,
                    latest_revision=revision,
                    skip_phase="coalesce",
                )
        if pointer_active:
            self._record_scheduler_event("deferred_for_pointer")
            log_reorder_drag_event(
                "preview_scheduler.deferred_for_pointer",
                gesture_id=gesture_id,
                event_id=event_id,
                reason=reason,
                revision=revision,
                pointer_revision=self._scheduled_pointer_revision,
            )
        self._timer.start(self._interval_ms)
        self._record_scheduler_event("requested")
        log_reorder_drag_timing(
            "preview_scheduler.requested",
            started_at=started_at,
            gesture_id=gesture_id,
            event_id=event_id,
            reason=reason,
            revision=revision,
            pointer_active=pointer_active,
            timer_was_active=was_active,
            interval_ms=self._interval_ms,
            scheduled_revision=self._scheduled_revision,
            pointer_revision=self._scheduled_pointer_revision,
        )

    def stop(self) -> None:
        """Stop any pending preview scheduler tick."""

        if self._timer.isActive():
            self._timer.stop()
        self._clear_pending()

    def is_active(self) -> bool:
        """Return whether a preview scheduler tick is pending."""

        return self._timer.isActive()

    def _run(self) -> None:
        """Run the latest pending preview work from the timer callback."""

        started_at = reorder_drag_started_at()
        scheduled_revision = self._scheduled_revision
        latest_revision = self._latest_requested_revision
        reason = self._latest_reason
        gesture_id = self._latest_gesture_id
        event_id = self._latest_event_id
        pending_age_ms = self._pending_age_ms()
        if scheduled_revision is None or latest_revision is None:
            log_reorder_drag_timing(
                "preview_scheduler.ran",
                started_at=started_at,
                gesture_id=gesture_id,
                event_id=event_id,
                reason=reason,
                ran=False,
                no_pending=True,
            )
            return
        if scheduled_revision < latest_revision:
            self._record_scheduler_event("skipped_stale")
            log_reorder_drag_event(
                "preview_scheduler.skipped_stale",
                gesture_id=gesture_id,
                event_id=event_id,
                reason=reason,
                skipped_revision=scheduled_revision,
                latest_revision=latest_revision,
                skip_phase="timer",
            )
            self._scheduled_revision = latest_revision
            self._scheduled_pointer_revision = self._current_pointer_revision()
            self._timer.start(self._interval_ms)
            return
        current_pointer_revision = self._current_pointer_revision()
        pointer_moved_since_request = (
            self._scheduled_pointer_revision is not None
            and current_pointer_revision is not None
            and current_pointer_revision > self._scheduled_pointer_revision
        )
        if pointer_moved_since_request and pending_age_ms < _POINTER_DEFER_CAP_MS:
            self._record_scheduler_event("rescheduled_after_pointer")
            log_reorder_drag_event(
                "preview_scheduler.rescheduled_after_pointer",
                gesture_id=gesture_id,
                event_id=event_id,
                reason=reason,
                scheduled_revision=scheduled_revision,
                latest_revision=latest_revision,
                pointer_revision=current_pointer_revision,
                scheduled_pointer_revision=self._scheduled_pointer_revision,
                pending_age_ms=f"{pending_age_ms:.3f}",
                cap_ms=f"{_POINTER_DEFER_CAP_MS:.3f}",
            )
            self._scheduled_pointer_revision = current_pointer_revision
            self._timer.start(self._interval_ms)
            return
        if pointer_moved_since_request:
            self._record_scheduler_event("starvation_cap_reached")
            log_reorder_drag_event(
                "preview_scheduler.starvation_cap_reached",
                gesture_id=gesture_id,
                event_id=event_id,
                reason=reason,
                scheduled_revision=scheduled_revision,
                latest_revision=latest_revision,
                pointer_revision=current_pointer_revision,
                scheduled_pointer_revision=self._scheduled_pointer_revision,
                pending_age_ms=f"{pending_age_ms:.3f}",
                cap_ms=f"{_POINTER_DEFER_CAP_MS:.3f}",
            )
        self._run_pending()
        self._record_scheduler_event("ran")
        elapsed_ms = log_reorder_drag_timing(
            "preview_scheduler.ran",
            started_at=started_at,
            gesture_id=gesture_id,
            event_id=event_id,
            reason=reason,
            ran=True,
            scheduled_revision=scheduled_revision,
            latest_revision=latest_revision,
            pending_age_ms=f"{pending_age_ms:.3f}",
        )
        self._record_scheduler_event("ran_latest")
        log_reorder_drag_event(
            "preview_scheduler.ran_latest",
            gesture_id=gesture_id,
            event_id=event_id,
            reason=reason,
            scheduled_revision=scheduled_revision,
            latest_revision=latest_revision,
            elapsed_ms=f"{elapsed_ms:.3f}",
        )
        if elapsed_ms >= 8.0:
            log_reorder_drag_event(
                "budget.preview_scheduler_run_exceeded",
                gesture_id=gesture_id,
                event_id=event_id,
                reason=reason,
                elapsed_ms=f"{elapsed_ms:.3f}",
                threshold_ms="8.000",
                scheduled_revision=scheduled_revision,
                latest_revision=latest_revision,
            )
        self._clear_pending()

    def _current_pointer_revision(self) -> int | None:
        """Return the latest pointer work-unit revision when one is available."""

        if self._pointer_revision is None:
            return None
        return self._pointer_revision()

    def _pending_age_ms(self) -> float:
        """Return how long the current preview request has been pending."""

        if self._pending_since is None:
            return 0.0
        return (perf_counter() - self._pending_since) * 1000.0

    def _record_scheduler_event(self, event: str) -> None:
        """Forward one scheduler classification to the active gesture summary."""

        if self._record_event is None:
            return
        self._record_event(event)

    def _clear_pending(self) -> None:
        """Forget pending scheduler state after a run or cancellation."""

        self._latest_requested_revision = None
        self._scheduled_revision = None
        self._latest_reason = None
        self._pending_since = None
        self._latest_request_at = None
        self._scheduled_pointer_revision = None
        self._latest_gesture_id = None
        self._latest_event_id = None


class PromptReorderPreviewSyncController:
    """Own pending preview sync bookkeeping and coalescing decisions."""

    def __init__(
        self,
        *,
        interval_ms: int,
        run_sync: Callable[[], None],
        pointer_revision: Callable[[], int | None] | None = None,
        record_scheduler_event: Callable[[str], None] | None = None,
        timer_factory: Callable[[], object] | None = None,
    ) -> None:
        """Initialize a latest-wins preview sync owner."""

        self._interval_ms = interval_ms
        self._run_sync = run_sync
        self._revision = 0
        self._pending_revision: int | None = None
        self._pending_reason: str | None = None
        self._pending_context: PromptReorderPreviewSyncContext | None = None
        self._pending_record_elapsed: Callable[[float], None] | None = None
        self._active_reason: str | None = None
        self._last_applied_revision = 0
        self._scheduler = PromptReorderPreviewScheduler(
            interval_ms=interval_ms,
            run_pending=self.flush_pending,
            timer_factory=timer_factory,
            pointer_revision=pointer_revision,
            record_event=record_scheduler_event,
        )

    @property
    def active_reason(self) -> str | None:
        """Return the reason attached to the sync currently being applied."""

        return self._active_reason

    @property
    def state(self) -> PromptReorderPreviewSyncState:
        """Return immutable preview-sync bookkeeping for tests."""

        return PromptReorderPreviewSyncState(
            revision=self._revision,
            pending_revision=self._pending_revision,
            pending_reason=self._pending_reason,
            active_reason=self._active_reason,
            last_applied_revision=self._last_applied_revision,
            scheduler_active=self._scheduler.is_active(),
        )

    def has_pending(self) -> bool:
        """Return whether a preview sync request is waiting to run."""

        return self._pending_revision is not None

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
        self._revision += 1
        self._pending_revision = self._revision
        self._pending_reason = reason
        self._pending_context = context
        self._pending_record_elapsed = record_elapsed
        if context.requires_immediate_drag_geometry:
            record_decision(True)
            log_reorder_drag_event(
                "preview_sync.immediate_base_geometry_missing",
                gesture_id=context.gesture_id,
                event_id=context.event_id,
                reason=reason,
                revision=self._revision,
            )
            log_reorder_drag_timing(
                "interaction.schedule_preview_sync.immediate",
                started_at=started_at,
                gesture_id=context.gesture_id,
                event_id=context.event_id,
                reason=reason,
                revision=self._revision,
                dragged_segment_index=context.dragged_segment_index,
            )
            self.flush_pending(reason="drag_reorder_prepare", forced=True)
            return
        record_decision(False)
        self._scheduler.request(
            revision=self._revision,
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
                revision=self._revision,
            )
        log_reorder_drag_timing(
            "interaction.schedule_preview_sync.deferred",
            started_at=started_at,
            gesture_id=context.gesture_id,
            event_id=context.event_id,
            reason=reason,
            revision=self._revision,
            timer_active=self._scheduler.is_active(),
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
        pending_revision = self._pending_revision
        if pending_revision is None:
            log_reorder_drag_timing(
                "interaction.flush_preview_sync.noop",
                started_at=started_at,
                gesture_id=gesture_id,
                event_id=event_id,
                reason=reason,
                forced=forced,
            )
            return
        pending_reason = self._pending_reason
        pending_context = context or self._pending_context
        pending_record_elapsed = record_elapsed or self._pending_record_elapsed
        self._pending_revision = None
        self._pending_reason = None
        self._pending_context = None
        self._pending_record_elapsed = None
        gesture_id = None if pending_context is None else pending_context.gesture_id
        event_id = None if pending_context is None else pending_context.event_id
        if self._scheduler.is_active():
            self._scheduler.stop()
        if pending_revision <= self._last_applied_revision:
            log_reorder_drag_event(
                "preview_scheduler.skipped_stale",
                gesture_id=gesture_id,
                event_id=event_id,
                reason=reason,
                pending_reason=pending_reason,
                pending_revision=pending_revision,
                last_applied_revision=self._last_applied_revision,
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
                last_applied_revision=self._last_applied_revision,
            )
            return
        self._active_reason = pending_reason
        try:
            self._run_sync()
        finally:
            self._active_reason = None
        self._last_applied_revision = pending_revision
        preview_sync_elapsed_ms = log_reorder_drag_timing(
            "interaction.flush_preview_sync.total",
            started_at=started_at,
            gesture_id=gesture_id,
            event_id=event_id,
            reason=reason,
            pending_reason=pending_reason,
            forced=forced,
            pending_revision=pending_revision,
            last_applied_revision=self._last_applied_revision,
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

        self._pending_revision = None
        self._pending_reason = None
        self._pending_context = None
        self._pending_record_elapsed = None
        if self._scheduler.is_active():
            self._scheduler.stop()

    def replace_state(
        self,
        *,
        pending_revision: int | None = None,
        pending_reason: str | None = None,
        last_applied_revision: int | None = None,
    ) -> None:
        """Replace preview-sync bookkeeping from a prepared scheduler state."""

        self._pending_revision = pending_revision
        self._pending_reason = pending_reason
        self._pending_context = None
        self._pending_record_elapsed = None
        if last_applied_revision is not None:
            self._last_applied_revision = last_applied_revision


__all__ = [
    "PromptReorderPreviewScheduler",
    "PromptReorderPreviewSyncContext",
    "PromptReorderPreviewSyncController",
    "PromptReorderPreviewSyncState",
]

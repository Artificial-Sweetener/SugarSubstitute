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

"""Adapt Qt timer wake-ups to reorder preview scheduling policy."""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter

from PySide6.QtCore import QObject, QTimer

from substitute.application.prompt_editor.reorder.preview_schedule import (
    PromptReorderPreviewSchedulePolicy,
    PromptReorderPreviewTimerDecision,
    preview_request_deferred_for_pointer,
    preview_request_rejected_stale_revision,
    preview_request_was_coalesced,
)
from substitute.shared.diagnostics.prompt_editor_work import (
    PromptEditorWorkEvent,
    prompt_editor_work_event,
)

from ..projection.observability import (
    log_reorder_drag_event,
    log_reorder_drag_timing,
    reorder_drag_started_at,
)

_POINTER_DEFER_CAP_MS = 96.0
_SLOW_TIMER_RUN_MS = 8.0

type PromptReorderPreviewTimerFactory = Callable[[], QTimer]


class PromptReorderPreviewTimer(QObject):
    """Wake the latest eligible reorder preview without owning its policy."""

    def __init__(
        self,
        *,
        interval_ms: int,
        run_pending: Callable[[], None],
        timer_factory: PromptReorderPreviewTimerFactory | None = None,
        pointer_revision: Callable[[], int | None] | None = None,
        record_event: Callable[[str], None] | None = None,
        parent: QObject | None = None,
    ) -> None:
        """Initialize one Qt wake-up adapter and its application policy."""

        super().__init__(parent)
        self._interval_ms = interval_ms
        self._run_pending = run_pending
        self._pointer_revision = pointer_revision
        self._record_event = record_event
        self._timer = (timer_factory or QTimer)()
        self._timer.setSingleShot(True)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._run)
        self._policy = PromptReorderPreviewSchedulePolicy(
            pointer_defer_cap_ms=_POINTER_DEFER_CAP_MS
        )
        self._reason: str | None = None
        self._gesture_id: int | None = None
        self._event_id: int | None = None

    @prompt_editor_work_event(PromptEditorWorkEvent.REORDER_PREVIEW_REQUEST)
    def request(
        self,
        *,
        revision: int,
        reason: str,
        pointer_active: bool,
        gesture_id: int | None,
        event_id: int | None,
    ) -> None:
        """Schedule one wake-up while application policy rejects older work."""

        started_at = reorder_drag_started_at()
        timer_was_active = self._timer.isActive()
        decision = self._policy.request(
            revision=revision,
            pointer_active=pointer_active,
            pointer_revision=self._current_pointer_revision(),
            timer_active=timer_was_active,
            now=perf_counter(),
        )
        self._reason = reason
        self._gesture_id = gesture_id
        self._event_id = event_id
        if timer_was_active:
            self._timer.stop()
        if preview_request_was_coalesced(decision):
            self._record_scheduler_event("coalesced")
            log_reorder_drag_event(
                "preview_scheduler.coalesced",
                gesture_id=gesture_id,
                event_id=event_id,
                reason=reason,
                revision=revision,
                previous_scheduled_revision=self._policy.replaced_revision,
            )
        if preview_request_rejected_stale_revision(decision):
            self._record_scheduler_event("skipped_stale")
            log_reorder_drag_event(
                "preview_scheduler.skipped_stale",
                gesture_id=gesture_id,
                event_id=event_id,
                reason=reason,
                skipped_revision=self._policy.replaced_revision,
                latest_revision=revision,
                skip_phase="coalesce",
            )
        if preview_request_deferred_for_pointer(decision):
            self._record_scheduler_event("deferred_for_pointer")
            log_reorder_drag_event(
                "preview_scheduler.deferred_for_pointer",
                gesture_id=gesture_id,
                event_id=event_id,
                reason=reason,
                revision=revision,
                pointer_revision=self._policy.scheduled_pointer_revision,
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
            timer_was_active=timer_was_active,
            interval_ms=self._interval_ms,
            scheduled_revision=self._policy.scheduled_revision,
            pointer_revision=self._policy.scheduled_pointer_revision,
        )

    def stop(self) -> None:
        """Stop the Qt wake-up and clear application schedule state."""

        if self._timer.isActive():
            self._timer.stop()
        self._clear()

    def is_active(self) -> bool:
        """Return whether the Qt adapter has a pending wake-up."""

        return self._timer.isActive()

    @prompt_editor_work_event(PromptEditorWorkEvent.REORDER_PREVIEW_RUN)
    def _run(self) -> None:
        """Apply one policy decision produced for a Qt timer wake-up."""

        started_at = reorder_drag_started_at()
        now = perf_counter()
        scheduled_revision = self._policy.scheduled_revision
        latest_revision = self._policy.latest_requested_revision
        scheduled_pointer_revision = self._policy.scheduled_pointer_revision
        pointer_revision = self._current_pointer_revision()
        pending_age_ms = self._policy.pending_age_ms(now=now)
        decision = self._policy.timer_decision(
            pointer_revision=pointer_revision,
            now=now,
        )
        if decision is PromptReorderPreviewTimerDecision.NO_PENDING:
            log_reorder_drag_timing(
                "preview_scheduler.ran",
                started_at=started_at,
                gesture_id=self._gesture_id,
                event_id=self._event_id,
                reason=self._reason,
                ran=False,
                no_pending=True,
            )
            return
        if decision is PromptReorderPreviewTimerDecision.RESCHEDULE_STALE:
            self._record_scheduler_event("skipped_stale")
            log_reorder_drag_event(
                "preview_scheduler.skipped_stale",
                gesture_id=self._gesture_id,
                event_id=self._event_id,
                reason=self._reason,
                skipped_revision=scheduled_revision,
                latest_revision=latest_revision,
                skip_phase="timer",
            )
            self._timer.start(self._interval_ms)
            return
        if decision is PromptReorderPreviewTimerDecision.RESCHEDULE_POINTER:
            self._record_scheduler_event("rescheduled_after_pointer")
            log_reorder_drag_event(
                "preview_scheduler.rescheduled_after_pointer",
                gesture_id=self._gesture_id,
                event_id=self._event_id,
                reason=self._reason,
                scheduled_revision=scheduled_revision,
                latest_revision=latest_revision,
                pointer_revision=pointer_revision,
                scheduled_pointer_revision=scheduled_pointer_revision,
                pending_age_ms=f"{pending_age_ms:.3f}",
                cap_ms=f"{_POINTER_DEFER_CAP_MS:.3f}",
            )
            self._timer.start(self._interval_ms)
            return
        if decision is PromptReorderPreviewTimerDecision.RUN_AFTER_STARVATION:
            self._record_scheduler_event("starvation_cap_reached")
            log_reorder_drag_event(
                "preview_scheduler.starvation_cap_reached",
                gesture_id=self._gesture_id,
                event_id=self._event_id,
                reason=self._reason,
                scheduled_revision=scheduled_revision,
                latest_revision=latest_revision,
                pointer_revision=pointer_revision,
                scheduled_pointer_revision=scheduled_pointer_revision,
                pending_age_ms=f"{pending_age_ms:.3f}",
                cap_ms=f"{_POINTER_DEFER_CAP_MS:.3f}",
            )
        self._run_pending()
        self._record_scheduler_event("ran")
        elapsed_ms = log_reorder_drag_timing(
            "preview_scheduler.ran",
            started_at=started_at,
            gesture_id=self._gesture_id,
            event_id=self._event_id,
            reason=self._reason,
            ran=True,
            scheduled_revision=scheduled_revision,
            latest_revision=latest_revision,
            pending_age_ms=f"{pending_age_ms:.3f}",
        )
        self._record_scheduler_event("ran_latest")
        log_reorder_drag_event(
            "preview_scheduler.ran_latest",
            gesture_id=self._gesture_id,
            event_id=self._event_id,
            reason=self._reason,
            scheduled_revision=scheduled_revision,
            latest_revision=latest_revision,
            elapsed_ms=f"{elapsed_ms:.3f}",
        )
        if elapsed_ms >= _SLOW_TIMER_RUN_MS:
            log_reorder_drag_event(
                "budget.preview_scheduler_run_exceeded",
                gesture_id=self._gesture_id,
                event_id=self._event_id,
                reason=self._reason,
                elapsed_ms=f"{elapsed_ms:.3f}",
                threshold_ms=f"{_SLOW_TIMER_RUN_MS:.3f}",
                scheduled_revision=scheduled_revision,
                latest_revision=latest_revision,
            )
        self._clear()

    def _current_pointer_revision(self) -> int | None:
        """Return the current pointer work revision when one is available."""

        if self._pointer_revision is None:
            return None
        return self._pointer_revision()

    def _record_scheduler_event(self, event: str) -> None:
        """Forward one scheduler classification to active diagnostics."""

        if self._record_event is not None:
            self._record_event(event)

    def _clear(self) -> None:
        """Forget application policy and diagnostic metadata."""

        self._policy.clear()
        self._reason = None
        self._gesture_id = None
        self._event_id = None


__all__ = ["PromptReorderPreviewTimer", "PromptReorderPreviewTimerFactory"]

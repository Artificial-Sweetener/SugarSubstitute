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

"""Coalesce safe prompt projection rebuilds onto GUI-thread frame slots."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter

from PySide6.QtCore import QObject, QTimer, Slot
from shiboken6 import isValid

from substitute.application.prompt_editor import (
    PromptDocumentView,
    PromptSyntaxRenderPlan,
)
from substitute.presentation.ui_load_activity import (
    default_prompt_projection_ui_load_activity,
)
from substitute.shared.logging.logger import get_logger, log_debug


_FIXED_PROJECTION_UPDATE_INTERVAL_MS = 0
_SAFE_TYPING_REASON = "safe_typing"
_LOGGER = get_logger("presentation.editor.prompt_editor.projection.update_scheduler")


@dataclass(frozen=True, slots=True)
class PromptProjectionScheduleContext:
    """Describe one pending projection scheduling decision."""

    reason: str
    pending_age_ms: float
    prompt_activity_elapsed_ms: float | None
    output_activity_elapsed_ms: float | None
    pending_superseded_count: int
    stale_safe: bool


@dataclass(frozen=True, slots=True)
class PromptProjectionScheduleDecision:
    """Carry the selected projection delay and diagnostics."""

    delay_ms: int
    force_due_to_max_stale: bool
    prompt_activity_recent: bool
    output_activity_recent: bool
    reason: str


@dataclass(frozen=True, slots=True)
class PromptProjectionSchedulingPolicy:
    """Choose when safe prompt projection work should land on the GUI thread."""

    active_typing_delay_ms: int = 180
    output_busy_delay_ms: int = 240
    idle_delay_ms: int = 0
    max_stale_ms: int = 750
    recent_prompt_activity_ms: int = 150
    recent_output_activity_ms: int = 150

    def choose_delay(
        self,
        context: PromptProjectionScheduleContext,
    ) -> PromptProjectionScheduleDecision:
        """Return the delay that best preserves prompt responsiveness."""

        prompt_activity_recent = self._prompt_activity_recent(context)
        output_activity_recent = self._output_activity_recent(context)
        if not context.stale_safe:
            return PromptProjectionScheduleDecision(
                delay_ms=self.idle_delay_ms,
                force_due_to_max_stale=False,
                prompt_activity_recent=prompt_activity_recent,
                output_activity_recent=output_activity_recent,
                reason="not_stale_safe",
            )
        if context.pending_age_ms >= self.max_stale_ms:
            return PromptProjectionScheduleDecision(
                delay_ms=self.idle_delay_ms,
                force_due_to_max_stale=True,
                prompt_activity_recent=prompt_activity_recent,
                output_activity_recent=output_activity_recent,
                reason="max_stale",
            )
        if prompt_activity_recent and output_activity_recent:
            return PromptProjectionScheduleDecision(
                delay_ms=max(0, self.output_busy_delay_ms),
                force_due_to_max_stale=False,
                prompt_activity_recent=True,
                output_activity_recent=True,
                reason="prompt_and_output_active",
            )
        if prompt_activity_recent:
            return PromptProjectionScheduleDecision(
                delay_ms=max(0, self.active_typing_delay_ms),
                force_due_to_max_stale=False,
                prompt_activity_recent=True,
                output_activity_recent=False,
                reason="prompt_active",
            )
        return PromptProjectionScheduleDecision(
            delay_ms=max(0, self.idle_delay_ms),
            force_due_to_max_stale=False,
            prompt_activity_recent=False,
            output_activity_recent=output_activity_recent,
            reason="idle",
        )

    def _prompt_activity_recent(
        self,
        context: PromptProjectionScheduleContext,
    ) -> bool:
        """Return whether prompt activity should bias projection later."""

        if context.reason == _SAFE_TYPING_REASON:
            return True
        elapsed_ms = context.prompt_activity_elapsed_ms
        return elapsed_ms is not None and elapsed_ms <= self.recent_prompt_activity_ms

    def _output_activity_recent(
        self,
        context: PromptProjectionScheduleContext,
    ) -> bool:
        """Return whether output/canvas work should bias projection later."""

        elapsed_ms = context.output_activity_elapsed_ms
        return elapsed_ms is not None and elapsed_ms <= self.recent_output_activity_ms


@dataclass(frozen=True, slots=True)
class PendingProjectionUpdate:
    """Capture the latest prompt projection inputs waiting for GUI flush."""

    document_view: PromptDocumentView
    render_plan: PromptSyntaxRenderPlan
    reason: str
    source_revision: int
    queued_at: float
    previous_document_view: PromptDocumentView | None = None
    previous_render_plan: PromptSyntaxRenderPlan | None = None

    @classmethod
    def create(
        cls,
        *,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
        reason: str,
        source_revision: int,
        previous_document_view: PromptDocumentView | None = None,
        previous_render_plan: PromptSyntaxRenderPlan | None = None,
    ) -> "PendingProjectionUpdate":
        """Build a pending update using the current monotonic timestamp."""

        return cls(
            document_view=document_view,
            render_plan=render_plan,
            reason=reason,
            source_revision=source_revision,
            queued_at=perf_counter(),
            previous_document_view=previous_document_view,
            previous_render_plan=previous_render_plan,
        )


class PromptProjectionUpdateScheduler(QObject):
    """Coalesce safe prompt projection rebuilds onto a GUI-thread frame slot."""

    def __init__(
        self,
        *,
        apply_update: Callable[[PendingProjectionUpdate], None],
        interval_ms: int | None = None,
        scheduling_policy: PromptProjectionSchedulingPolicy | None = None,
        prompt_activity_elapsed_ms: Callable[[], float | None] | None = None,
        output_activity_elapsed_ms: Callable[[], float | None] | None = None,
        parent: QObject | None = None,
    ) -> None:
        """Create a latest-wins scheduler for prompt projection updates."""

        super().__init__(parent)
        self._apply_update = apply_update
        self._fixed_interval_ms = (
            None if interval_ms is None else max(0, int(interval_ms))
        )
        self._interval_ms = (
            _FIXED_PROJECTION_UPDATE_INTERVAL_MS
            if self._fixed_interval_ms is None
            else self._fixed_interval_ms
        )
        self._scheduling_policy = (
            scheduling_policy or PromptProjectionSchedulingPolicy()
        )
        self._prompt_activity_elapsed_ms = (
            prompt_activity_elapsed_ms or _prompt_activity_elapsed_unknown
        )
        self._output_activity_elapsed_ms = (
            output_activity_elapsed_ms
            or default_prompt_projection_ui_load_activity().output_activity_elapsed_ms
        )
        self._pending_update: PendingProjectionUpdate | None = None
        self._pending_started_at: float | None = None
        self._pending_superseded_count = 0
        self._qt_destroyed = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(self._interval_ms)
        self._timer.timeout.connect(self._flush_due)
        self.destroyed.connect(self._mark_destroyed)

    def schedule(self, update: PendingProjectionUpdate) -> None:
        """Schedule one projection update, replacing any older pending update."""

        previous_update = self._pending_update
        if previous_update is None:
            self._pending_started_at = update.queued_at
            self._pending_superseded_count = 0
        else:
            self._pending_superseded_count += 1
        self._pending_update = update
        decision = self._schedule_decision(update)
        timer_active = self._timer_is_active()
        if not self._timer_is_operational():
            self._drop_pending_after_dead_timer(operation="schedule")
            return
        self._interval_ms = decision.delay_ms
        self._timer.setInterval(self._interval_ms)
        timer_restarted = bool(
            timer_active
            and self._should_restart_active_typing_timer(
                update=update,
                decision=decision,
            )
        )
        _log_projection_update_scheduled(
            update,
            decision=decision,
            pending_age_ms=self._pending_age_ms(update),
            pending_superseded_count=self._pending_superseded_count,
            timer_was_active=timer_active,
            timer_restarted=timer_restarted,
        )
        if not timer_active:
            self._timer.start()
            return
        if timer_restarted:
            self._timer.stop()
            self._timer.start(self._interval_ms)
            return
        remaining_ms = self._timer_remaining_time()
        if remaining_ms < 0 or remaining_ms <= self._interval_ms:
            return
        self._timer.stop()
        self._timer.start(self._interval_ms)

    def _should_restart_active_typing_timer(
        self,
        *,
        update: PendingProjectionUpdate,
        decision: PromptProjectionScheduleDecision,
    ) -> bool:
        """Return whether a fresh typing update should extend the idle catch-up timer."""

        return bool(
            self._fixed_interval_ms is None
            and update.reason == _SAFE_TYPING_REASON
            and decision.prompt_activity_recent
            and not decision.force_due_to_max_stale
        )

    def flush_now(self, *, reason: str) -> None:
        """Synchronously apply any pending update before exact geometry reads."""

        pending_update = self._pending_update
        if pending_update is None:
            return
        if not self._timer_is_operational():
            self._drop_pending_after_dead_timer(operation="flush_now")
            return
        if self._timer_is_active():
            self._timer.stop()
        self._flush_pending(reason=reason)

    def cancel(self) -> None:
        """Drop any pending update without applying it."""

        self._pending_update = None
        self._pending_started_at = None
        self._pending_superseded_count = 0
        if not self._timer_is_operational():
            return
        if self._timer_is_active():
            self._timer.stop()

    def cancel_if_stale_safe_source_unchanged(self, source_text: str) -> bool:
        """Drop stale-safe pending work when it does not carry new source text."""

        pending_update = self._pending_update
        if (
            pending_update is None
            or pending_update.reason != _SAFE_TYPING_REASON
            or pending_update.document_view.source_text != source_text
        ):
            return False
        self.cancel()
        return True

    def has_pending_update(self) -> bool:
        """Return whether a projection update is waiting to flush."""

        if not self._timer_is_operational():
            return False
        return self._pending_update is not None

    @Slot()
    def _flush_due(self) -> None:
        """Apply the latest scheduled update when the timer fires."""

        if not self._timer_is_operational():
            self._drop_pending_after_dead_timer(operation="flush_due")
            return
        self._flush_pending(reason="scheduled")

    def _flush_pending(self, *, reason: str) -> None:
        """Apply and clear the pending update, if one exists."""

        pending_update = self._pending_update
        if pending_update is None:
            return
        pending_age_ms = self._pending_age_ms(pending_update)
        pending_superseded_count = self._pending_superseded_count
        self._pending_update = None
        self._pending_started_at = None
        self._pending_superseded_count = 0
        log_debug(
            _LOGGER,
            "prompt_projection_update.flushed",
            flush_reason=reason,
            update_reason=pending_update.reason,
            pending_age_ms=f"{pending_age_ms:.3f}",
            pending_superseded_count=pending_superseded_count,
        )
        self._apply_update(pending_update)

    @Slot()
    def _mark_destroyed(self) -> None:
        """Remember that Qt has started destroying this scheduler."""

        self._qt_destroyed = True
        self._pending_update = None
        self._pending_started_at = None
        self._pending_superseded_count = 0

    def _timer_is_operational(self) -> bool:
        """Return whether the owned Qt timer can still be called."""

        if self._qt_destroyed:
            return False
        try:
            return bool(isValid(self._timer))
        except RuntimeError:
            return False
        except TypeError:
            return True

    def _timer_is_active(self) -> bool:
        """Return whether the timer is active without surfacing Qt deletion errors."""

        if not self._timer_is_operational():
            return False
        try:
            return bool(self._timer.isActive())
        except RuntimeError:
            return False

    def _timer_remaining_time(self) -> int:
        """Return remaining timer time or expired when Qt has deleted the timer."""

        if not self._timer_is_operational():
            return -1
        try:
            return int(self._timer.remainingTime())
        except RuntimeError:
            return -1

    def _drop_pending_after_dead_timer(self, *, operation: str) -> None:
        """Clear pending work when Qt teardown has already deleted the timer."""

        _ = operation
        self._pending_update = None
        self._pending_started_at = None
        self._pending_superseded_count = 0

    def _schedule_decision(
        self,
        update: PendingProjectionUpdate,
    ) -> PromptProjectionScheduleDecision:
        """Return the adaptive or fixed delay for a pending update."""

        if self._fixed_interval_ms is not None:
            return PromptProjectionScheduleDecision(
                delay_ms=self._fixed_interval_ms,
                force_due_to_max_stale=False,
                prompt_activity_recent=False,
                output_activity_recent=False,
                reason="fixed_interval",
            )
        prompt_activity_elapsed_ms = self._prompt_activity_elapsed_ms()
        if update.reason == _SAFE_TYPING_REASON and prompt_activity_elapsed_ms is None:
            prompt_activity_elapsed_ms = 0.0
        context = PromptProjectionScheduleContext(
            reason=update.reason,
            pending_age_ms=self._pending_age_ms(update),
            prompt_activity_elapsed_ms=prompt_activity_elapsed_ms,
            output_activity_elapsed_ms=self._output_activity_elapsed_ms(),
            pending_superseded_count=self._pending_superseded_count,
            stale_safe=update.reason == _SAFE_TYPING_REASON,
        )
        return self._scheduling_policy.choose_delay(context)

    def _pending_age_ms(self, update: PendingProjectionUpdate) -> float:
        """Return elapsed milliseconds since the oldest pending projection update."""

        started_at = self._pending_started_at or update.queued_at
        return max(0.0, (perf_counter() - started_at) * 1000.0)


def _prompt_activity_elapsed_unknown() -> float | None:
    """Return unknown prompt activity when no provider is installed."""

    return None


def _log_projection_update_scheduled(
    update: PendingProjectionUpdate,
    *,
    decision: PromptProjectionScheduleDecision,
    pending_age_ms: float,
    pending_superseded_count: int,
    timer_was_active: bool,
    timer_restarted: bool,
) -> None:
    """Emit one projection-update scheduling diagnostic event."""

    log_debug(
        _LOGGER,
        "prompt_projection_update.scheduled",
        update_reason=update.reason,
        decision_reason=decision.reason,
        delay_ms=decision.delay_ms,
        force_due_to_max_stale=decision.force_due_to_max_stale,
        prompt_activity_recent=decision.prompt_activity_recent,
        output_activity_recent=decision.output_activity_recent,
        pending_age_ms=f"{pending_age_ms:.3f}",
        pending_superseded_count=pending_superseded_count,
        stale_safe=update.reason == _SAFE_TYPING_REASON,
        timer_was_active=timer_was_active,
        timer_restarted=timer_restarted,
    )


__all__ = [
    "PendingProjectionUpdate",
    "PromptProjectionScheduleContext",
    "PromptProjectionScheduleDecision",
    "PromptProjectionSchedulingPolicy",
    "PromptProjectionUpdateScheduler",
]

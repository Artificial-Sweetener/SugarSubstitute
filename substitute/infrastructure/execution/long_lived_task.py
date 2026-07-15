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

"""Manage one long-lived cancellable execution task."""

from __future__ import annotations

from collections.abc import Callable
import logging
import threading
import time
from typing import Generic, Protocol, TypeVar

from substitute.application.execution import (
    CancellationSource,
    ExecutionContext,
    TaskIdentity,
    TaskOutcome,
    TaskTimings,
)

TResult = TypeVar("TResult")
LongLivedWork = Callable[[CancellationSource], TResult]


class LongLivedDispatcher(Protocol):
    """Publish long-lived task callbacks on an owner thread."""

    def publish(self, callback: Callable[[], None], *, reason: str) -> None:
        """Queue one owner-thread callback."""


class LongLivedTaskHandle(Generic[TResult]):
    """Own exactly one long-running callable and its stop lifecycle."""

    def __init__(
        self,
        *,
        identity: TaskIdentity,
        context: ExecutionContext,
        work: LongLivedWork[TResult],
        dispatcher: LongLivedDispatcher,
        close_hook: Callable[[], None] | None = None,
        join_timeout_seconds: float = 1.0,
        thread_name: str,
        logger: logging.Logger | None = None,
    ) -> None:
        """Start one long-lived callable immediately."""

        _require_non_blank(thread_name, field_name="thread_name")
        _require_non_negative_float(
            join_timeout_seconds,
            field_name="join_timeout_seconds",
        )
        self._identity = identity
        self._context = context
        self._work = work
        self._dispatcher = dispatcher
        self._close_hook = close_hook
        self._join_timeout_seconds = join_timeout_seconds
        self._logger = logger or logging.getLogger(__name__)
        self._cancellation = CancellationSource(
            generation=identity.cancellation_generation
        )
        self._queued_at = time.monotonic()
        self._started_at: float | None = None
        self._outcome: TaskOutcome[TResult] | None = None
        self._callbacks: list[tuple[Callable[[TaskOutcome[TResult]], None], str]] = []
        self._late_stop = False
        self._lock = threading.Lock()
        self._thread = threading.Thread(
            target=self._run,
            name=thread_name,
            daemon=True,
        )
        self._logger.info(
            "Long-lived execution task starting.",
            extra=self._log_extra(status="starting"),
        )
        self._thread.start()

    @property
    def identity(self) -> TaskIdentity:
        """Return this task identity."""

        return self._identity

    @property
    def is_finished(self) -> bool:
        """Return whether the long-lived task has settled."""

        with self._lock:
            return self._outcome is not None

    @property
    def outcome(self) -> TaskOutcome[TResult] | None:
        """Return the terminal outcome when available."""

        with self._lock:
            return self._outcome

    @property
    def state(self) -> str:
        """Return the current lifecycle state."""

        with self._lock:
            outcome = self._outcome
        if outcome is not None:
            return outcome.status
        if self._thread.is_alive():
            return "running"
        return "pending"

    @property
    def late_stop(self) -> bool:
        """Return whether the task missed the configured stop timeout."""

        with self._lock:
            return self._late_stop

    def add_done_callback(
        self,
        callback: Callable[[TaskOutcome[TResult]], None],
        *,
        reason: str,
    ) -> None:
        """Publish one callback when the task completes."""

        _require_non_blank(reason, field_name="reason")
        with self._lock:
            outcome = self._outcome
            if outcome is None:
                self._callbacks.append((callback, reason))
                return
        self._publish_callback(callback, reason=reason, outcome=outcome)

    def stop(self, *, reason: str) -> None:
        """Request cancellation, call the close hook, and join briefly."""

        _require_non_blank(reason, field_name="reason")
        self._logger.info(
            "Long-lived execution task stop requested.",
            extra=self._log_extra(status="stop_requested", cancellation_reason=reason),
        )
        self._cancellation.cancel(reason=reason)
        if self._close_hook is not None:
            try:
                self._close_hook()
            except BaseException as error:  # noqa: BLE001
                self._logger.error(
                    "Long-lived execution close hook failed.",
                    extra=self._log_extra(status="close_failed"),
                    exc_info=error,
                )
            else:
                self._logger.debug(
                    "Long-lived execution close hook completed.",
                    extra=self._log_extra(status="close_completed"),
                )
        self._thread.join(self._join_timeout_seconds)
        if self._thread.is_alive():
            with self._lock:
                self._late_stop = True
            self._logger.warning(
                "Long-lived execution task did not stop before timeout.",
                extra=self._log_extra(
                    status="late_stop",
                    cancellation_reason=reason,
                ),
            )

    def cancel(self, *, reason: str) -> None:
        """Request cancellation using the standard task-handle method name."""

        self.stop(reason=reason)

    def _run(self) -> None:
        """Run the long-lived callable and publish its terminal outcome."""

        started_at = time.monotonic()
        with self._lock:
            self._started_at = started_at
        try:
            result = self._work(self._cancellation)
        except BaseException as error:  # noqa: BLE001
            completed_at = time.monotonic()
            outcome: TaskOutcome[TResult] = TaskOutcome(
                identity=self._identity,
                context=self._context,
                status="failed",
                error=error,
                timings=TaskTimings(
                    queued_at=self._queued_at,
                    started_at=started_at,
                    completed_at=completed_at,
                ),
            )
        else:
            completed_at = time.monotonic()
            if self._cancellation.is_cancelled:
                outcome = TaskOutcome(
                    identity=self._identity,
                    context=self._context,
                    status="cancelled",
                    cancellation_reason=self._cancellation.reason or "cancelled",
                    timings=TaskTimings(
                        queued_at=self._queued_at,
                        started_at=started_at,
                        completed_at=completed_at,
                    ),
                )
            else:
                outcome = TaskOutcome(
                    identity=self._identity,
                    context=self._context,
                    status="succeeded",
                    result=result,
                    timings=TaskTimings(
                        queued_at=self._queued_at,
                        started_at=started_at,
                        completed_at=completed_at,
                    ),
                )
        self._finish(outcome)

    def _finish(self, outcome: TaskOutcome[TResult]) -> None:
        """Store and publish one terminal outcome."""

        with self._lock:
            if self._outcome is not None:
                return
            self._outcome = outcome
            callbacks = tuple(self._callbacks)
            self._callbacks.clear()
        self._logger.info(
            "Long-lived execution task completed.",
            extra=self._log_extra(
                status=outcome.status,
                cancellation_reason=outcome.cancellation_reason,
            ),
            exc_info=outcome.error,
        )
        for callback, reason in callbacks:
            self._publish_callback(callback, reason=reason, outcome=outcome)

    def _publish_callback(
        self,
        callback: Callable[[TaskOutcome[TResult]], None],
        *,
        reason: str,
        outcome: TaskOutcome[TResult],
    ) -> None:
        """Queue one terminal callback through the dispatcher."""

        self._dispatcher.publish(lambda: callback(outcome), reason=reason)

    def _log_extra(
        self,
        *,
        status: str,
        cancellation_reason: str | None = None,
    ) -> dict[str, object]:
        """Return safe structured log fields for this task."""

        return {
            "operation": self._context.operation,
            "reason": self._context.reason,
            "lane": self._context.lane,
            "request_id": self._identity.request_id,
            "status": status,
            "cancellation_reason": cancellation_reason,
        }


def _require_non_blank(value: str, *, field_name: str) -> None:
    """Reject blank lifecycle labels."""

    if not value.strip():
        raise ValueError(f"{field_name} must not be blank.")


def _require_non_negative_float(value: float, *, field_name: str) -> None:
    """Reject negative timeout settings."""

    if value < 0:
        raise ValueError(f"{field_name} must be non-negative.")


__all__ = [
    "LongLivedTaskHandle",
    "LongLivedWork",
]

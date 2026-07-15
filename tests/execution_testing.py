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

"""Provide deterministic execution fakes for tests."""

from __future__ import annotations

from collections.abc import Callable
from threading import Lock
from typing import Generic, TypeVar

from substitute.application.execution.cancellation import (
    CancellationSource,
    CancellationToken,
    NeverCancelled,
)
from substitute.application.execution.executor import TaskRequest
from substitute.application.execution.identity import TaskIdentity
from substitute.application.execution.outcome import TaskOutcome, TaskTimings

TResult = TypeVar("TResult")


class ManualTaskHandle(Generic[TResult]):
    """Expose manual task completion for deterministic tests."""

    def __init__(self, request: TaskRequest[TResult]) -> None:
        """Create a pending manual handle for one request."""

        self._request = request
        self._outcome: TaskOutcome[TResult] | None = None
        self._callbacks: list[tuple[Callable[[TaskOutcome[TResult]], None], str]] = []
        self._state = "pending"
        self._cancel_reason: str | None = None
        self._lock = Lock()

    @property
    def identity(self) -> TaskIdentity:
        """Return the task identity associated with this handle."""

        return self._request.identity

    @property
    def is_finished(self) -> bool:
        """Return whether this handle has been completed."""

        with self._lock:
            return self._outcome is not None

    @property
    def outcome(self) -> TaskOutcome[TResult] | None:
        """Return the manual outcome when one has been supplied."""

        with self._lock:
            return self._outcome

    @property
    def state(self) -> str:
        """Return the current manual state."""

        with self._lock:
            return self._state

    @property
    def cancel_reason(self) -> str | None:
        """Return the last cancellation reason supplied by a test."""

        with self._lock:
            return self._cancel_reason

    def add_done_callback(
        self,
        callback: Callable[[TaskOutcome[TResult]], None],
        *,
        reason: str,
    ) -> None:
        """Register or immediately publish one done callback."""

        _require_non_blank(reason, field_name="reason")
        with self._lock:
            outcome = self._outcome
            if outcome is None:
                self._callbacks.append((callback, reason))
                return
        callback(outcome)

    def cancel(self, *, reason: str) -> None:
        """Mark cancellation requested and complete when not already settled."""

        _require_non_blank(reason, field_name="reason")
        with self._lock:
            self._cancel_reason = reason
            if self._outcome is not None:
                return
        self.complete_cancelled(reason=reason)

    def complete_success(self, result: TResult) -> None:
        """Complete this handle with a successful result."""

        self._complete(
            TaskOutcome(
                identity=self._request.identity,
                context=self._request.context,
                status="succeeded",
                result=result,
            )
        )

    def complete_failed(self, error: BaseException) -> None:
        """Complete this handle with a failed result."""

        self._complete(
            TaskOutcome(
                identity=self._request.identity,
                context=self._request.context,
                status="failed",
                error=error,
            )
        )

    def complete_cancelled(self, *, reason: str) -> None:
        """Complete this handle as cancelled."""

        _require_non_blank(reason, field_name="reason")
        self._complete(
            TaskOutcome(
                identity=self._request.identity,
                context=self._request.context,
                status="cancelled",
                cancellation_reason=reason,
            )
        )

    def _complete(self, outcome: TaskOutcome[TResult]) -> None:
        """Publish one outcome once."""

        with self._lock:
            if self._outcome is not None:
                raise RuntimeError("manual task handle is already complete.")
            self._outcome = outcome
            self._state = outcome.status
            callbacks = tuple(self._callbacks)
            self._callbacks.clear()
        for callback, _reason in callbacks:
            callback(outcome)


class ImmediateTaskSubmitter:
    """Run submitted work synchronously and return a settled handle."""

    def submit(
        self,
        request: TaskRequest[TResult],
        *,
        cancellation: CancellationToken,
    ) -> ManualTaskHandle[TResult]:
        """Execute one task immediately for deterministic tests."""

        handle: ManualTaskHandle[TResult] = ManualTaskHandle(request)
        if cancellation.is_cancelled:
            handle.complete_cancelled(reason=cancellation.reason or "cancelled")
            return handle
        try:
            result = request.work(cancellation)
        except BaseException as error:  # noqa: BLE001
            handle.complete_failed(error)
        else:
            handle.complete_success(result)
        return handle


class QueuedTaskSubmitter:
    """Queue submitted requests until tests complete them manually."""

    def __init__(self) -> None:
        """Create an empty queued submitter."""

        self._handles: list[ManualTaskHandle[object]] = []
        self._cancellations: list[CancellationToken] = []

    @property
    def handles(self) -> tuple[ManualTaskHandle[object], ...]:
        """Return queued manual handles."""

        return tuple(self._handles)

    @property
    def cancellations(self) -> tuple[CancellationToken, ...]:
        """Return cancellation tokens supplied for queued requests."""

        return tuple(self._cancellations)

    def submit(
        self,
        request: TaskRequest[TResult],
        *,
        cancellation: CancellationToken,
    ) -> ManualTaskHandle[TResult]:
        """Queue one request and return a manual handle."""

        handle: ManualTaskHandle[TResult] = ManualTaskHandle(request)
        self._handles.append(_as_object_handle(handle))
        self._cancellations.append(cancellation)
        return handle


class RecordingDispatcher:
    """Record callbacks and reasons for dispatcher adapter tests."""

    def __init__(self) -> None:
        """Create an empty callback log."""

        self._callbacks: list[tuple[Callable[[], None], str]] = []

    @property
    def callbacks(self) -> tuple[tuple[Callable[[], None], str], ...]:
        """Return recorded callbacks and reasons."""

        return tuple(self._callbacks)

    def publish(self, callback: Callable[[], None], *, reason: str) -> None:
        """Record one publication request."""

        _require_non_blank(reason, field_name="reason")
        self._callbacks.append((callback, reason))

    def run_all(self) -> None:
        """Run recorded callbacks in submission order."""

        callbacks = tuple(self._callbacks)
        self._callbacks.clear()
        for callback, _reason in callbacks:
            callback()


class FakeCancellationSource(CancellationSource):
    """Expose a named fake cancellation source for tests."""


def settled_success_outcome(
    request: TaskRequest[TResult],
    result: TResult,
) -> TaskOutcome[TResult]:
    """Build a successful test outcome for one request."""

    return TaskOutcome(
        identity=request.identity,
        context=request.context,
        status="succeeded",
        result=result,
        timings=TaskTimings(),
    )


def never_cancelled() -> NeverCancelled:
    """Return a neutral cancellation token for tests."""

    return NeverCancelled()


def _as_object_handle(handle: ManualTaskHandle[TResult]) -> ManualTaskHandle[object]:
    """Return a manual handle widened for queued-submit bookkeeping."""

    return handle  # type: ignore[return-value]


def _require_non_blank(value: str, *, field_name: str) -> None:
    """Reject blank testing adapter labels."""

    if not value.strip():
        raise ValueError(f"{field_name} must not be blank.")


__all__ = [
    "FakeCancellationSource",
    "ImmediateTaskSubmitter",
    "ManualTaskHandle",
    "QueuedTaskSubmitter",
    "RecordingDispatcher",
    "never_cancelled",
    "settled_success_outcome",
]

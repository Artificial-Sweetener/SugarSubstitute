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

"""Own execution task lifetime for one application or presentation scope."""

from __future__ import annotations

from threading import Lock
from typing import TypeVar

from .cancellation import CancellationController, CancellationSource
from .executor import TaskHandle, TaskRequest, TaskSubmitter

TResult = TypeVar("TResult")


class TaskScope:
    """Track submitted handles and cancel them when the owner closes."""

    def __init__(
        self,
        *,
        submitter: TaskSubmitter,
        scope_id: str,
        cancellation_controller: CancellationController | None = None,
    ) -> None:
        """Create a task scope for one owner lifetime."""

        _require_non_blank(scope_id, field_name="scope_id")
        self._submitter = submitter
        self._scope_id = scope_id
        self._cancellation_controller = (
            cancellation_controller or CancellationController()
        )
        self._handles: set[TaskHandle[object]] = set()
        self._sources: dict[TaskHandle[object], CancellationSource] = {}
        self._closed = False
        self._lock = Lock()

    @property
    def scope_id(self) -> str:
        """Return the scope identifier used in execution context."""

        return self._scope_id

    @property
    def is_closed(self) -> bool:
        """Return whether the owner has closed this scope."""

        with self._lock:
            return self._closed

    def has_pending_work(self) -> bool:
        """Return whether any tracked handle has not settled."""

        with self._lock:
            return any(not handle.is_finished for handle in self._handles)

    def submit(self, request: TaskRequest[TResult]) -> TaskHandle[TResult]:
        """Submit one request and track it until completion or scope close."""

        source = self._cancellation_controller.next_source()
        scoped_request = TaskRequest(
            identity=request.identity.with_cancellation_generation(source.generation),
            context=request.context,
            work=request.work,
        )
        with self._lock:
            if self._closed:
                raise RuntimeError(f"Task scope {self._scope_id} is closed.")
        handle = self._submitter.submit(scoped_request, cancellation=source)
        object_handle = _as_object_handle(handle)
        with self._lock:
            if self._closed:
                source.cancel(reason="scope_closed")
                handle.cancel(reason="scope_closed")
                return handle
            self._handles.add(object_handle)
            self._sources[object_handle] = source
        handle.add_done_callback(
            lambda _outcome: self._forget_handle(object_handle),
            reason="task_scope_completed",
        )
        return handle

    def cancel_all(self, *, reason: str) -> None:
        """Cancel every tracked task without closing this scope."""

        _require_non_blank(reason, field_name="reason")
        with self._lock:
            pairs = tuple(
                (handle, self._sources.get(handle)) for handle in self._handles
            )
        for handle, source in pairs:
            if source is not None:
                source.cancel(reason=reason)
            handle.cancel(reason=reason)

    def close(self, *, reason: str) -> None:
        """Close this scope and cancel tracked tasks."""

        _require_non_blank(reason, field_name="reason")
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self.cancel_all(reason=reason)

    def _forget_handle(self, handle: TaskHandle[object]) -> None:
        """Stop retaining a handle after it has settled."""

        with self._lock:
            self._handles.discard(handle)
            self._sources.pop(handle, None)


def _as_object_handle(handle: TaskHandle[TResult]) -> TaskHandle[object]:
    """Return a task handle widened for internal scope bookkeeping."""

    return handle  # type: ignore[return-value]


def _require_non_blank(value: str, *, field_name: str) -> None:
    """Reject blank task-scope labels."""

    if not value.strip():
        raise ValueError(f"{field_name} must not be blank.")


__all__ = [
    "TaskScope",
]

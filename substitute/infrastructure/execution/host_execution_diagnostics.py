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

"""Coalesce host execution diagnostics away from scheduler critical sections."""

from __future__ import annotations

import logging
from collections.abc import Callable
from threading import Condition, Lock, Thread

from sugarsubstitute_shared.crash_reporting.runtime import (
    report_active_execution_exception,
)
from substitute.infrastructure.execution.host_execution_model import (
    HostExecutionSnapshot,
)


class HostDiagnosticsSubscription:
    """Release one host diagnostics observer idempotently."""

    def __init__(self, close: Callable[[], None]) -> None:
        """Store the observer removal operation."""

        self._close = close
        self._closed = False
        self._lock = Lock()

    def close(self) -> None:
        """Remove the observer once."""

        with self._lock:
            if self._closed:
                return
            self._closed = True
        self._close()


class HostExecutionDiagnostics:
    """Deliver only the newest physical snapshot on a lazy host thread."""

    def __init__(
        self,
        *,
        thread_name: str,
        logger: logging.Logger,
    ) -> None:
        """Create an idle diagnostics owner without starting a thread."""

        self._thread_name = thread_name
        self._logger = logger
        self._observers: dict[int, Callable[[HostExecutionSnapshot], None]] = {}
        self._next_observer_id = 0
        self._latest: HostExecutionSnapshot | None = None
        self._thread: Thread | None = None
        self._closed = False
        self._condition = Condition(Lock())

    def publish(self, snapshot: HostExecutionSnapshot) -> None:
        """Replace the pending snapshot when observers exist."""

        with self._condition:
            if self._closed or not self._observers:
                return
            self._latest = snapshot
            self._condition.notify()

    def subscribe(
        self,
        callback: Callable[[HostExecutionSnapshot], None],
    ) -> HostDiagnosticsSubscription:
        """Register an observer and lazily start coalesced delivery."""

        with self._condition:
            if self._closed:
                raise RuntimeError("host execution diagnostics are closed")
            self._next_observer_id += 1
            observer_id = self._next_observer_id
            self._observers[observer_id] = callback
            if self._thread is None:
                self._thread = Thread(
                    target=self._run,
                    name=self._thread_name,
                    daemon=True,
                )
                self._thread.start()
        return HostDiagnosticsSubscription(lambda: self._unsubscribe(observer_id))

    def close(self, *, wait: bool) -> None:
        """Stop delivery and release every observer."""

        with self._condition:
            if not self._closed:
                self._closed = True
                self._latest = None
                self._observers.clear()
                self._condition.notify_all()
            thread = self._thread
        if wait and thread is not None:
            thread.join()

    def _run(self) -> None:
        """Deliver coalesced snapshots until shutdown."""

        while True:
            with self._condition:
                while self._latest is None and not self._closed:
                    self._condition.wait()
                if self._closed:
                    return
                snapshot = self._latest
                self._latest = None
                observers = tuple(self._observers.values())
            if snapshot is None:
                continue
            for observer in observers:
                try:
                    observer(snapshot)
                except Exception as error:
                    self._logger.exception(
                        "Host execution diagnostics observer failed."
                    )
                    if report_active_execution_exception(error):
                        return

    def _unsubscribe(self, observer_id: int) -> None:
        """Remove one observer without affecting other subscriptions."""

        with self._condition:
            self._observers.pop(observer_id, None)
            if not self._observers:
                self._latest = None


__all__ = ["HostDiagnosticsSubscription", "HostExecutionDiagnostics"]

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

"""Provide owned threaded-task support for managed-process contracts."""

from __future__ import annotations

import threading

from substitute.application.execution import (
    CancellationSource,
    ExecutionContext,
    TaskIdentity,
)
from substitute.infrastructure.comfy import managed_launcher


class _ThreadedManagedTaskHandle:
    """Run one managed-process task inside its test-owned thread."""

    def __init__(
        self,
        work: managed_launcher.LongLivedWork[None],
        *,
        thread_name: str,
    ) -> None:
        """Start the supplied long-lived work immediately."""

        self._cancellation = CancellationSource(generation=1)
        self._thread = threading.Thread(target=lambda: work(self._cancellation))
        self._thread.name = thread_name
        self._thread.start()

    @property
    def is_finished(self) -> bool:
        """Return whether the work thread has exited."""

        return not self._thread.is_alive()

    def stop(self, *, reason: str) -> None:
        """Cancel and briefly join the work thread."""

        self._cancellation.cancel(reason=reason)
        self._thread.join(timeout=1.0)

    def join(self, *, timeout: float) -> None:
        """Join the work thread for tests that wait on startup."""

        self._thread.join(timeout=timeout)


def _managed_task_factory(
    identity: TaskIdentity,
    context: ExecutionContext,
    work: managed_launcher.LongLivedWork[None],
    thread_name: str,
) -> managed_launcher.ManagedLongLivedTaskHandle:
    """Create one test-owned managed long-lived task."""

    _ = identity, context
    return _ThreadedManagedTaskHandle(work, thread_name=thread_name)

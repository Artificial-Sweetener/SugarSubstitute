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

"""Gate minimum shell readiness on pre-interactive startup prerequisites."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Protocol

from substitute.app.bootstrap.ready_shell_restore_controller import (
    mark_minimum_shell_ready,
)
from substitute.app.bootstrap.startup_trace import trace_mark

_PREREQUISITE_POLL_INTERVAL_MS = 10


class ReadyShellMinimumReadyStateProtocol(Protocol):
    """Expose the minimum shell readiness flag."""

    minimum_shell_ready: bool


def mark_ready_shell_minimum_ready_task(
    *,
    startup_cancelled: bool,
    state: ReadyShellMinimumReadyStateProtocol,
    try_show_main_window: Callable[[], None],
    trace_fields: Callable[[], Mapping[str, object]],
    after_mark_ready: Callable[[], object] | None = None,
) -> bool:
    """Run the ready-shell minimum-readiness queue task and update state."""

    return bool(
        mark_minimum_shell_ready(
            startup_cancelled=startup_cancelled,
            mark_ready=lambda: setattr(state, "minimum_shell_ready", True),
            try_show_main_window=try_show_main_window,
            trace_fields=trace_fields,
            after_mark_ready=after_mark_ready,
        )
    )


class ReadyShellMinimumReadyTask:
    """Defer shell reveal until every pre-interactive prerequisite settles."""

    def __init__(
        self,
        *,
        startup_cancelled: Callable[[], bool],
        state: ReadyShellMinimumReadyStateProtocol,
        try_show_main_window: Callable[[], None],
        trace_fields: Callable[[], Mapping[str, object]],
        after_mark_ready: Callable[[], object] | None = None,
        prerequisite_ready: Callable[[], bool] | None = None,
        scheduler: Callable[[int, Callable[[], None]], None] | None = None,
    ) -> None:
        """Store readiness, reveal, and bounded event-loop deferral ports."""

        if prerequisite_ready is not None and scheduler is None:
            raise ValueError("minimum-ready prerequisite requires a scheduler")
        self._startup_cancelled = startup_cancelled
        self._state = state
        self._try_show_main_window = try_show_main_window
        self._after_mark_ready = after_mark_ready
        self._prerequisite_ready = prerequisite_ready
        self._scheduler = scheduler
        self._trace_fields = trace_fields

    def run(self) -> None:
        """Mark readiness now or yield until its prerequisite settles."""

        if self._startup_cancelled():
            self.mark_ready()
            return
        prerequisite_ready = self._prerequisite_ready
        if prerequisite_ready is not None and not prerequisite_ready():
            scheduler = self._scheduler
            if scheduler is None:
                raise RuntimeError("minimum-ready prerequisite scheduler is missing")
            trace_mark(
                "mark_minimum_shell_ready_task.deferred",
                reason="prerequisite_pending",
                **dict(self._trace_fields()),
            )
            scheduler(_PREREQUISITE_POLL_INTERVAL_MS, self._retained_retry())
            return
        self.mark_ready()

    def _retained_retry(self) -> Callable[[], None]:
        """Keep this task alive until Qt invokes its deferred retry."""

        def retry() -> None:
            self.run()

        return retry

    def mark_ready(self) -> bool:
        """Mark the shell ready using current startup cancellation state."""

        return mark_ready_shell_minimum_ready_task(
            startup_cancelled=self._startup_cancelled(),
            state=self._state,
            try_show_main_window=self._try_show_main_window,
            after_mark_ready=self._after_mark_ready,
            trace_fields=self._trace_fields,
        )


def create_ready_shell_minimum_ready_task(
    *,
    startup_cancelled: Callable[[], bool],
    state: ReadyShellMinimumReadyStateProtocol,
    try_show_main_window: Callable[[], None],
    trace_fields: Callable[[], Mapping[str, object]],
    after_mark_ready: Callable[[], object] | None = None,
    prerequisite_ready: Callable[[], bool] | None = None,
    scheduler: Callable[[int, Callable[[], None]], None] | None = None,
) -> ReadyShellMinimumReadyTask:
    """Create one prerequisite-aware minimum-shell readiness task."""

    return ReadyShellMinimumReadyTask(
        startup_cancelled=startup_cancelled,
        state=state,
        try_show_main_window=try_show_main_window,
        after_mark_ready=after_mark_ready,
        prerequisite_ready=prerequisite_ready,
        scheduler=scheduler,
        trace_fields=trace_fields,
    )


__all__ = [
    "ReadyShellMinimumReadyStateProtocol",
    "ReadyShellMinimumReadyTask",
    "create_ready_shell_minimum_ready_task",
    "mark_ready_shell_minimum_ready_task",
]

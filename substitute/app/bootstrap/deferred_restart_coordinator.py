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

"""Defer managed runtime restarts until generation work is safe."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol, cast

from substitute.shared.logging.logger import (
    get_logger,
    log_info,
    log_warning,
    log_warning_exception,
)

_LOGGER = get_logger("app.bootstrap.deferred_restart_coordinator")


class ObservableGenerationQueue(Protocol):
    """Describe queue state needed to defer a destructive restart."""

    def has_cancellable_jobs(self) -> bool:
        """Return whether shutdown would terminate generation work."""

    def add_observer(self, observer: Callable[[object], None]) -> None:
        """Observe queue state changes."""

    def remove_observer(self, observer: Callable[[object], None]) -> None:
        """Stop observing queue state changes."""


class DeferredRestartCoordinator:
    """Coalesce restart requests and begin shutdown only at a safe boundary."""

    def __init__(
        self,
        *,
        queue_provider: Callable[[], object | None],
        begin_restart: Callable[[], None],
        restart_command: Sequence[str],
    ) -> None:
        """Store restart safety ports without owning shell lifecycle."""

        self._queue_provider = queue_provider
        self._begin_restart = begin_restart
        self._restart_command = tuple(restart_command)
        self._requested = False
        self._observed_queue: ObservableGenerationQueue | None = None

    @property
    def requested(self) -> bool:
        """Return whether one restart request has been accepted."""

        return self._requested

    def request(self) -> None:
        """Accept one restart request or refuse unsafe unobservable work."""

        if self._requested:
            log_info(_LOGGER, "Duplicate ComfyUI restart request ignored")
            return
        candidate = self._queue_provider()
        has_jobs = getattr(candidate, "has_cancellable_jobs", None)
        try:
            active_work = callable(has_jobs) and bool(has_jobs())
        except Exception as error:
            log_warning_exception(
                _LOGGER,
                "ComfyUI restart refused because generation safety was unreadable",
                error=error,
                queue_type=type(candidate).__name__,
            )
            return
        if not active_work:
            self._requested = True
            self._begin_restart()
            return
        add_observer = getattr(candidate, "add_observer", None)
        remove_observer = getattr(candidate, "remove_observer", None)
        if not callable(add_observer) or not callable(remove_observer):
            log_warning(
                _LOGGER,
                "ComfyUI restart refused while generation work is active",
                queue_type=type(candidate).__name__,
            )
            return
        queue = cast(ObservableGenerationQueue, candidate)
        self._requested = True
        self._observed_queue = queue
        try:
            queue.add_observer(self._handle_queue_change)
        except Exception as error:
            self._requested = False
            self._observed_queue = None
            log_warning_exception(
                _LOGGER,
                "ComfyUI restart refused because queue observation failed",
                error=error,
                queue_type=type(candidate).__name__,
            )
            return
        if self._observed_queue is not None:
            log_info(
                _LOGGER,
                "ComfyUI restart deferred until generation queue is safe",
                command=self._restart_command,
            )

    def _handle_queue_change(self, _change: object) -> None:
        """Begin the accepted restart when the observed queue drains."""

        queue = self._observed_queue
        if queue is None:
            return
        try:
            active_work = queue.has_cancellable_jobs()
        except Exception as error:
            log_warning_exception(
                _LOGGER,
                "Deferred ComfyUI restart remains pending because queue safety failed",
                error=error,
                queue_type=type(queue).__name__,
            )
            return
        if active_work:
            return
        self._observed_queue = None
        try:
            queue.remove_observer(self._handle_queue_change)
        except Exception as error:
            log_warning_exception(
                _LOGGER,
                "Generation queue observer cleanup failed before safe restart",
                error=error,
                queue_type=type(queue).__name__,
            )
        self._begin_restart()


__all__ = ["DeferredRestartCoordinator", "ObservableGenerationQueue"]

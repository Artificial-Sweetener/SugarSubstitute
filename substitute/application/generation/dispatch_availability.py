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

"""Own Comfy-dependent generation dispatch availability."""

from __future__ import annotations

from collections.abc import Callable

from substitute.shared.logging.logger import get_logger, log_info

_LOGGER = get_logger("application.generation.dispatch_availability")


class GenerationDispatchAvailability:
    """Gate queue dispatch and publish connection loss before queue advancement."""

    def __init__(
        self,
        *,
        resume_dispatch: Callable[[], None],
        pending_job_count: Callable[[], int],
        active_job_id: Callable[[], str | None],
    ) -> None:
        """Store queue observation ports and initialize dispatch as available."""

        self._resume_dispatch = resume_dispatch
        self._pending_job_count = pending_job_count
        self._active_job_id = active_job_id
        self._available = True
        self._connection_lost_handler: Callable[[], None] | None = None

    @property
    def available(self) -> bool:
        """Return whether new pending work may be dispatched."""

        return self._available

    def set_available(self, available: bool) -> None:
        """Change dispatch availability and resume held work when restored."""

        if self._available == available:
            return
        self._available = available
        log_info(
            _LOGGER,
            "Generation queue dispatch availability changed",
            dispatch_available=available,
            pending_job_count=self._pending_job_count(),
            active_job_id=self._active_job_id(),
        )
        if available:
            self._resume_dispatch()

    def bind_connection_lost_handler(self, handler: Callable[[], None]) -> None:
        """Bind the outage transition that must precede queue advancement."""

        self._connection_lost_handler = handler

    def report_listener_failure(self, *, connection_lost: bool) -> None:
        """Publish typed connection loss before the queue marks a job failed."""

        if connection_lost and self._connection_lost_handler is not None:
            self._connection_lost_handler()


__all__ = ["GenerationDispatchAvailability"]

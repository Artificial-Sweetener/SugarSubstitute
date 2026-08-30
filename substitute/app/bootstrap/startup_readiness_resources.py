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

"""Define startup readiness resource ports and their retained lifetime."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from substitute.app.bootstrap.startup_probe_tasks import (
    ReadinessProbeResult,
    RuntimeCompatibilityProbeResult,
)


class TimerSignalProtocol(Protocol):
    """Describe the timer signal interface used by readiness orchestration."""

    def connect(self, callback: Callable[[], None]) -> None:
        """Connect one no-argument timeout callback."""


class ReadinessTimerProtocol(Protocol):
    """Describe the timer operations required by readiness orchestration."""

    timeout: TimerSignalProtocol

    def setInterval(self, interval_ms: int) -> None:
        """Set the timer interval in milliseconds."""

    def start(self) -> None:
        """Start or restart the timer."""

    def stop(self) -> None:
        """Stop the timer."""


class StartupReadinessProbeProtocol(Protocol):
    """Describe the readiness probe task surface used by the controller."""

    def connect_finished(
        self, callback: Callable[[ReadinessProbeResult], None]
    ) -> None:
        """Connect one readiness completion callback."""

    def request_probe(self, *, host: str, port: int) -> int | None:
        """Request one asynchronous readiness probe."""

    def accept_result(self, result: ReadinessProbeResult) -> bool:
        """Return whether a result is current and accepted."""

    def cancel_current(self) -> None:
        """Cancel the current probe result."""


class StartupRuntimeCompatibilityProbeProtocol(Protocol):
    """Describe the runtime compatibility probe surface used by the controller."""

    def connect_finished(
        self,
        callback: Callable[[RuntimeCompatibilityProbeResult], None],
    ) -> None:
        """Connect one compatibility completion callback."""

    def request_assessment(self) -> int | None:
        """Request one asynchronous compatibility assessment."""

    def accept_result(self, result: RuntimeCompatibilityProbeResult) -> bool:
        """Return whether a result is current and accepted."""

    def cancel_current(self) -> None:
        """Cancel the current compatibility result."""


class StartupReadinessStartProtocol(Protocol):
    """Start readiness polling."""

    def start(self) -> None:
        """Start readiness polling."""


class StartupReadinessStarter:
    """Late-bind readiness start/restart callbacks across startup controllers."""

    def __init__(self) -> None:
        """Initialize without a bound readiness controller."""

        self._controller: StartupReadinessStartProtocol | None = None

    def bind(self, controller: StartupReadinessStartProtocol) -> None:
        """Bind the readiness controller that owns timer startup."""

        self._controller = controller

    def start(self) -> None:
        """Start readiness through the bound controller."""

        if self._controller is None:
            raise RuntimeError("Startup readiness controller is not bound.")
        self._controller.start()


@dataclass(frozen=True)
class StartupReadinessResources:
    """Retain the single readiness resource set for one startup lifetime."""

    timer: ReadinessTimerProtocol
    readiness_probe: StartupReadinessProbeProtocol
    compatibility_probe: StartupRuntimeCompatibilityProbeProtocol


__all__ = (
    "ReadinessTimerProtocol",
    "StartupReadinessProbeProtocol",
    "StartupReadinessResources",
    "StartupReadinessStarter",
    "StartupReadinessStartProtocol",
    "StartupRuntimeCompatibilityProbeProtocol",
    "TimerSignalProtocol",
)

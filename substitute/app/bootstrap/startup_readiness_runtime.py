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

"""Adapt concrete startup readiness runtime resources for controllers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from substitute.app.bootstrap.startup_failure_controller import StartupTimerProtocol
from substitute.app.bootstrap.startup_probe_tasks import (
    StartupReadinessProbe,
    StartupRuntimeCompatibilityProbe,
)
from substitute.app.bootstrap.startup_qt_timers import create_startup_qtimer
from substitute.app.bootstrap.startup_readiness_controller import (
    ReadinessTimerProtocol,
    StartupReadinessProbeProtocol,
    StartupRuntimeCompatibilityProbeProtocol,
)
from substitute.app.bootstrap.startup_resources import StartupResourceRegistry
from substitute.app.bootstrap.startup_timing import StartupTimer
from substitute.application.backend_compatibility import BackendCompatibilityResult


class StartupReadinessRuntimeAdapters:
    """Own concrete readiness timers, probe registration, and timing ports."""

    def __init__(
        self,
        *,
        startup_resources: StartupResourceRegistry,
        startup_timer: StartupTimer,
        execution_runtime: Any,
        execution_dispatcher_factory: Callable[[], Any],
        timer_factory: Callable[[], Any] = create_startup_qtimer,
    ) -> None:
        """Create readiness runtime adapters for one startup lifetime."""

        self._startup_resources = startup_resources
        self._startup_timer = startup_timer
        self._execution_runtime = execution_runtime
        self._execution_dispatcher_factory = execution_dispatcher_factory
        self._timer_factory = timer_factory
        self._readiness_timers: list[StartupTimerProtocol] = []

    def create_readiness_timer(self) -> ReadinessTimerProtocol:
        """Create one concrete readiness timer."""

        return cast(ReadinessTimerProtocol, self._timer_factory())

    def create_readiness_probe(
        self,
        probe: Callable[[str, int], bool],
    ) -> StartupReadinessProbeProtocol:
        """Create one concrete readiness probe task."""

        submitter = self._execution_runtime.submitter(
            "startup",
            owner_id="startup_readiness_probe",
            dispatcher=self._execution_dispatcher_factory(),
        )
        return StartupReadinessProbe(
            probe=probe,
            submitter=submitter,
            close_submitter=submitter.close,
        )

    def create_runtime_compatibility_probe(
        self,
        assess: Callable[[], BackendCompatibilityResult | None],
    ) -> StartupRuntimeCompatibilityProbeProtocol:
        """Create one concrete runtime compatibility probe task."""

        submitter = self._execution_runtime.submitter(
            "startup",
            owner_id="startup_runtime_compatibility_probe",
            dispatcher=self._execution_dispatcher_factory(),
        )
        return StartupRuntimeCompatibilityProbe(
            assess=assess,
            submitter=submitter,
            close_submitter=submitter.close,
        )

    def register_timer(self, timer: ReadinessTimerProtocol) -> None:
        """Retain one readiness timer for fail-closed cleanup."""

        self._readiness_timers.append(timer)

    def readiness_timers(self) -> tuple[StartupTimerProtocol, ...]:
        """Return readiness timers retained for fail-closed cleanup."""

        return tuple(self._readiness_timers)

    def register_readiness_probe(
        self,
        probe: StartupReadinessProbeProtocol,
    ) -> None:
        """Register one long-lived readiness probe for startup cleanup."""

        self._startup_resources.register_readiness_probe(
            cast(StartupReadinessProbe, probe)
        )

    def register_runtime_compatibility_probe(
        self,
        probe: StartupRuntimeCompatibilityProbeProtocol,
    ) -> None:
        """Register one long-lived compatibility probe for startup cleanup."""

        self._startup_resources.register_runtime_compatibility_probe(
            cast(StartupRuntimeCompatibilityProbe, probe)
        )

    def mark_startup_timer(self, name: str) -> None:
        """Record one startup timing milestone."""

        self._startup_timer.mark(name)


__all__ = ["StartupReadinessRuntimeAdapters"]

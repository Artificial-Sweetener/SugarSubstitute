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

"""Record structured startup phase timings for bootstrap diagnostics."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
import time

from substitute.shared.logging.logger import get_logger, log_info

_LOGGER = get_logger("app.bootstrap.startup_timing")


@dataclass(frozen=True)
class StartupTimingRecord:
    """Describe one completed startup timing phase."""

    phase: str
    elapsed_ms: float


@dataclass(frozen=True)
class StartupMilestone:
    """Describe one point-in-time startup milestone from process start."""

    name: str
    elapsed_ms: float


class StartupTimer:
    """Measure named startup phases and emit structured duration logs."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        """Initialize the timer with an injectable monotonic clock."""

        self._clock = clock
        self._started_at = self._clock()
        self._records: list[StartupTimingRecord] = []
        self._milestones: list[StartupMilestone] = []

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        """Measure one named phase and log its duration on exit."""

        started_at = self._clock()
        try:
            yield
        finally:
            elapsed_ms = max(0.0, (self._clock() - started_at) * 1000.0)
            record = StartupTimingRecord(phase=name, elapsed_ms=elapsed_ms)
            self._records.append(record)
            log_info(
                _LOGGER,
                "Startup phase completed",
                phase=name,
                elapsed_ms=f"{elapsed_ms:.3f}",
            )

    def records(self) -> tuple[StartupTimingRecord, ...]:
        """Return completed timing records in emission order."""

        return tuple(self._records)

    def mark(self, name: str) -> StartupMilestone:
        """Record one startup milestone relative to timer construction."""

        elapsed_ms = max(0.0, (self._clock() - self._started_at) * 1000.0)
        milestone = StartupMilestone(name=name, elapsed_ms=elapsed_ms)
        self._milestones.append(milestone)
        log_info(
            _LOGGER,
            "Startup milestone recorded",
            milestone=name,
            elapsed_ms=f"{elapsed_ms:.3f}",
        )
        return milestone

    def milestones(self) -> tuple[StartupMilestone, ...]:
        """Return recorded startup milestones in emission order."""

        return tuple(self._milestones)

    def elapsed_ms_for_milestone(self, name: str) -> float | None:
        """Return the first matching milestone elapsed time when recorded."""

        for milestone in self._milestones:
            if milestone.name == name:
                return milestone.elapsed_ms
        return None

    def elapsed_ms_between(self, start: str, end: str) -> float | None:
        """Return elapsed milliseconds between two recorded milestones."""

        started_at = self.elapsed_ms_for_milestone(start)
        ended_at = self.elapsed_ms_for_milestone(end)
        if started_at is None or ended_at is None:
            return None
        return max(0.0, ended_at - started_at)


__all__ = ["StartupMilestone", "StartupTimer", "StartupTimingRecord"]

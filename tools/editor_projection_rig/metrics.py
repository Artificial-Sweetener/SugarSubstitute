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

"""Collect replay metrics for editor projection rig reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter


@dataclass(slots=True)
class MetricsRecorder:
    """Record counters and timings for one replay iteration."""

    counters: dict[str, int] = field(default_factory=dict)
    timings_ms: dict[str, float] = field(default_factory=dict)

    def increment(self, name: str, amount: int = 1) -> None:
        """Increment one named counter."""

        self.counters[name] = self.counters.get(name, 0) + amount

    def timed(self, name: str) -> "_Timer":
        """Return a context manager that records elapsed milliseconds."""

        return _Timer(self, name)


@dataclass(slots=True)
class _Timer:
    """Record elapsed time into a metrics recorder."""

    recorder: MetricsRecorder
    name: str
    started_at: float = 0.0

    def __enter__(self) -> None:
        """Start timing."""

        self.started_at = perf_counter()

    def __exit__(self, *_exc: object) -> None:
        """Store elapsed milliseconds."""

        elapsed = (perf_counter() - self.started_at) * 1000.0
        self.recorder.timings_ms[self.name] = round(elapsed, 3)

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

"""Record production-path editor projection events for rig reports."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any


@dataclass(frozen=True, slots=True)
class TraceEvent:
    """Describe one observed production-path projection event."""

    name: str
    at_ms: float
    duration_ms: float | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        """Return a JSON-compatible event payload."""

        payload: dict[str, Any] = {
            "name": self.name,
            "at_ms": round(self.at_ms, 3),
        }
        if self.duration_ms is not None:
            payload["duration_ms"] = round(self.duration_ms, 3)
        if self.details:
            payload["details"] = dict(self.details)
        return payload


@dataclass(slots=True)
class ProjectionTraceRecorder:
    """Collect counters, timings, and ordered events for one rig iteration."""

    counters: dict[str, int] = field(default_factory=dict)
    timings_ms: dict[str, float] = field(default_factory=dict)
    events: list[TraceEvent] = field(default_factory=list)
    started_at: float = field(default_factory=perf_counter)

    def increment(self, name: str, amount: int = 1) -> None:
        """Increment one named counter."""

        self.counters[name] = self.counters.get(name, 0) + amount

    def mark(self, name: str, **details: Any) -> None:
        """Record one instantaneous event."""

        self.events.append(
            TraceEvent(
                name=name,
                at_ms=(perf_counter() - self.started_at) * 1000.0,
                details=_clean_details(details),
            )
        )

    @contextmanager
    def timed(self, name: str, **details: Any) -> Iterator[None]:
        """Record elapsed time for a named phase and emit an ordered event."""

        phase_started_at = perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (perf_counter() - phase_started_at) * 1000.0
            self.timings_ms[name] = round(
                self.timings_ms.get(name, 0.0) + elapsed_ms,
                3,
            )
            self.events.append(
                TraceEvent(
                    name=name,
                    at_ms=(phase_started_at - self.started_at) * 1000.0,
                    duration_ms=elapsed_ms,
                    details=_clean_details(details),
                )
            )

    def to_json(self) -> dict[str, Any]:
        """Return a JSON-compatible trace summary."""

        return {
            "counters": dict(sorted(self.counters.items())),
            "timings_ms": dict(sorted(self.timings_ms.items())),
            "events": [event.to_json() for event in self.events],
        }


def _clean_details(details: Mapping[str, Any]) -> dict[str, Any]:
    """Return stable scalar trace details without Qt object payloads."""

    clean: dict[str, Any] = {}
    for key, value in details.items():
        if _is_json_scalar(value):
            clean[key] = value
        elif isinstance(value, tuple | list):
            clean[key] = [
                item if _is_json_scalar(item) else repr(item) for item in value
            ]
        else:
            clean[key] = repr(value)
    return clean


def _is_json_scalar(value: object) -> bool:
    """Return whether a value can be recorded directly in JSON traces."""

    return value is None or isinstance(value, bool | int | float | str)

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

"""Route Comfy prompt lifecycle events without listener side effects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol


class PromptLifecycleTimingTracker(Protocol):
    """Describe timing operations required by prompt lifecycle event routing."""

    def mark_prompt_started(self, timestamp_ms: float | None) -> None:
        """Record a prompt start timestamp."""

    def mark_prompt_terminal(self, timestamp_ms: float | None) -> None:
        """Record a prompt terminal timestamp."""


@dataclass(frozen=True)
class PromptLifecycleRouteResult:
    """Describe the listener action selected for one lifecycle event."""

    handled: bool
    interrupted: bool = False


def route_prompt_lifecycle_event(
    message_type: object,
    data: Mapping[str, object],
    *,
    active_prompt_id: str,
    timing_tracker: PromptLifecycleTimingTracker,
) -> PromptLifecycleRouteResult:
    """Apply prompt lifecycle timing for events targeting the active prompt."""

    if message_type == "execution_start":
        if data.get("prompt_id") == active_prompt_id:
            timing_tracker.mark_prompt_started(_optional_float(data.get("timestamp")))
        return PromptLifecycleRouteResult(handled=True)

    if message_type == "execution_success":
        if data.get("prompt_id") == active_prompt_id:
            timing_tracker.mark_prompt_terminal(_optional_float(data.get("timestamp")))
        return PromptLifecycleRouteResult(handled=True)

    if message_type == "execution_interrupted":
        if data.get("prompt_id") != active_prompt_id:
            return PromptLifecycleRouteResult(handled=True)
        timing_tracker.mark_prompt_terminal(_optional_float(data.get("timestamp")))
        return PromptLifecycleRouteResult(handled=True, interrupted=True)

    return PromptLifecycleRouteResult(handled=False)


def _optional_float(value: object) -> float | None:
    """Return numeric payload fields as floats when present."""

    if isinstance(value, (int, float)):
        return float(value)
    return None


__all__ = [
    "PromptLifecycleRouteResult",
    "PromptLifecycleTimingTracker",
    "route_prompt_lifecycle_event",
]

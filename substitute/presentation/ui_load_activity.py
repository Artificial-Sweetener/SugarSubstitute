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

"""Track recent presentation load that should influence UI scheduling."""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter


class PromptProjectionUiLoadActivity:
    """Record recent output/canvas work without changing that work's behavior."""

    def __init__(self, *, clock: Callable[[], float] = perf_counter) -> None:
        """Create a monotonic output-activity tracker."""

        self._clock = clock
        self._last_output_activity_at: float | None = None

    def mark_output_activity(self, *, reason: str) -> None:
        """Record one output/canvas activity boundary for scheduling decisions."""

        del reason
        self._last_output_activity_at = self._clock()

    def output_activity_elapsed_ms(self) -> float | None:
        """Return elapsed milliseconds since output/canvas activity was marked."""

        if self._last_output_activity_at is None:
            return None
        return max(0.0, (self._clock() - self._last_output_activity_at) * 1000.0)

    def is_output_activity_recent(self, *, within_ms: float) -> bool:
        """Return whether output/canvas work happened inside one recency window."""

        elapsed_ms = self.output_activity_elapsed_ms()
        return elapsed_ms is not None and elapsed_ms <= within_ms


_DEFAULT_PROMPT_PROJECTION_UI_LOAD_ACTIVITY = PromptProjectionUiLoadActivity()


def default_prompt_projection_ui_load_activity() -> PromptProjectionUiLoadActivity:
    """Return the process presentation-load tracker used by prompt projection."""

    return _DEFAULT_PROMPT_PROJECTION_UI_LOAD_ACTIVITY


__all__ = [
    "PromptProjectionUiLoadActivity",
    "default_prompt_projection_ui_load_activity",
]

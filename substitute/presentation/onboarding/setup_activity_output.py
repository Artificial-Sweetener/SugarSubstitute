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

"""Relay every setup record as activity while keeping its console concise."""

from __future__ import annotations

from collections.abc import Callable
import re

from sugarsubstitute_shared.localization import ApplicationText
from sugarsubstitute_shared.presentation.localization import render_application_text
from sugarsubstitute_shared.presentation.terminal.output_stream import (
    TerminalOutputStream,
)


_PERCENT_PROGRESS = re.compile(
    r"^(?P<operation>Copying managed Python packages|Extracting managed environment):"
    r".*?(?P<percentage>\d{1,3})%"
)
_NOISY_DEPENDENCY_PREFIX = "Requirement already satisfied:"


class SetupActivityOutput:
    """Own setup activity pulses, full diagnostics, and visible-log coalescing."""

    def __init__(
        self,
        *,
        stream: TerminalOutputStream,
        activity_observer: Callable[[], None],
        diagnostic_sink: Callable[[str], None],
    ) -> None:
        """Store the three output destinations with independent fidelity needs."""

        self._stream = stream
        self._activity_observer = activity_observer
        self._diagnostic_sink = diagnostic_sink
        self._progress_buckets: dict[str, int] = {}
        self._last_visible_line: str | None = None

    def begin_attempt(self) -> None:
        """Reset coalescing boundaries for a separate setup or repair attempt."""

        self._progress_buckets.clear()
        self._last_visible_line = None

    def accept(self, message: ApplicationText) -> None:
        """Pulse for every record and retain only useful console milestones."""

        line = render_application_text(message)
        self._activity_observer()
        self._diagnostic_sink(line)
        if not self._should_display(line):
            return
        self._stream.append_line(line)
        self._last_visible_line = line

    def _should_display(self, line: str) -> bool:
        """Return whether a raw setup record adds useful visible information."""

        stripped = line.lstrip()
        if stripped.startswith(_NOISY_DEPENDENCY_PREFIX):
            return False
        if line == self._last_visible_line:
            return False
        match = _PERCENT_PROGRESS.match(stripped)
        if match is None:
            return True
        percentage = min(100, int(match.group("percentage")))
        bucket = percentage // 10
        operation = match.group("operation")
        previous_bucket = self._progress_buckets.get(operation)
        if previous_bucket is not None and bucket <= previous_bucket:
            return False
        self._progress_buckets[operation] = bucket
        return True


__all__ = ["SetupActivityOutput"]

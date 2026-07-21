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

"""Measure external CPU pressure around special prompt-editor campaigns."""

from __future__ import annotations

import os
from time import perf_counter

import psutil  # type: ignore[import-untyped]

from .models import PromptAbuseSystemLoad


class PromptAbuseSystemLoadProbe:
    """Measure harness and competing CPU utilization over one campaign."""

    def __init__(self) -> None:
        """Capture process CPU time and initialize the system utilization sample."""

        self._started_at = perf_counter()
        self._process = psutil.Process()
        process_times = self._process.cpu_times()
        self._process_cpu_started = process_times.user + process_times.system
        self._logical_cpu_count = max(1, os.cpu_count() or 1)
        psutil.cpu_percent(interval=None)

    def finish(self) -> PromptAbuseSystemLoad:
        """Return normalized CPU pressure observed since probe construction."""

        elapsed_seconds = max(perf_counter() - self._started_at, 0.000001)
        process_times = self._process.cpu_times()
        process_cpu_seconds = max(
            0.0,
            process_times.user + process_times.system - self._process_cpu_started,
        )
        harness_cpu_percent = min(
            100.0,
            process_cpu_seconds / elapsed_seconds / self._logical_cpu_count * 100.0,
        )
        system_cpu_percent = float(psutil.cpu_percent(interval=None))
        return PromptAbuseSystemLoad(
            elapsed_seconds=elapsed_seconds,
            logical_cpu_count=self._logical_cpu_count,
            system_cpu_percent=system_cpu_percent,
            harness_cpu_percent=harness_cpu_percent,
            competing_cpu_percent=max(0.0, system_cpu_percent - harness_cpu_percent),
        )


__all__ = ["PromptAbuseSystemLoadProbe"]

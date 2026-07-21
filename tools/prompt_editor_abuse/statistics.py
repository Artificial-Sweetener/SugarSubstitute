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

"""Calculate stable latency summaries for prompt-editor abuse reports."""

from __future__ import annotations

from collections.abc import Sequence
import math

from .models import PromptAbuseLatencySummary


def summarize_latencies(values: Sequence[float]) -> PromptAbuseLatencySummary:
    """Return p50, p95, p99, and maximum latency for one sample set."""

    return PromptAbuseLatencySummary(
        p50_ms=percentile(values, 50),
        p95_ms=percentile(values, 95),
        p99_ms=percentile(values, 99),
        maximum_ms=max(values, default=0.0),
    )


def percentile(values: Sequence[float], percentile_rank: int) -> float:
    """Return the nearest-rank percentile for a possibly empty sample set."""

    if not 0 <= percentile_rank <= 100:
        raise ValueError("Percentile rank must be between zero and one hundred.")
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil((percentile_rank / 100.0) * len(ordered)))
    return ordered[rank - 1]


__all__ = ["percentile", "summarize_latencies"]

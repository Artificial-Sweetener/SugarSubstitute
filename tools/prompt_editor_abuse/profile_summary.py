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

"""Summarize profiler and counter evidence across abuse editor mounts."""

from __future__ import annotations

import cProfile
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
import pstats
from typing import cast

from .models import PromptAbuseHotspot

_HOTSPOT_LIMIT = 100
_CALLER_LIMIT = 5


def summarize_counts(values: list[str]) -> tuple[tuple[str, int], ...]:
    """Return deterministic most-common counts without empty reason labels."""

    return tuple(
        sorted(
            ((value or "<none>", count) for value, count in Counter(values).items()),
            key=lambda item: (-item[1], item[0]),
        )
    )


def summarize_hotspots(
    profiler: cProfile.Profile,
) -> tuple[PromptAbuseHotspot, ...]:
    """Return cumulative hotspots from one completed profiler capture."""

    return _summarize_stats(pstats.Stats(profiler))


def summarize_combined_hotspots(
    profilers: Sequence[cProfile.Profile],
) -> tuple[PromptAbuseHotspot, ...]:
    """Return cumulative hotspots merged from isolated action profiles."""

    if not profilers:
        return ()
    stats = pstats.Stats(profilers[0])
    for profiler in profilers[1:]:
        stats.add(profiler)
    return _summarize_stats(stats)


def _summarize_stats(stats: pstats.Stats) -> tuple[PromptAbuseHotspot, ...]:
    """Return ranked hotspots from prepared profiler statistics."""

    profile_stats = cast(
        Mapping[
            tuple[str, int, str],
            tuple[int, int, float, float, object],
        ],
        getattr(stats, "stats"),
    )
    ranked = sorted(
        profile_stats.items(),
        key=lambda item: item[1][3],
        reverse=True,
    )[:_HOTSPOT_LIMIT]
    return tuple(
        PromptAbuseHotspot(
            function=f"{Path(key[0]).name}:{key[1]}({key[2]})",
            call_count=values[1],
            own_time_ms=values[2] * 1_000.0,
            cumulative_time_ms=values[3] * 1_000.0,
            callers=_summarize_callers(values[4]),
        )
        for key, values in ranked
    )


def _summarize_callers(raw_callers: object) -> tuple[str, ...]:
    """Return the highest-cumulative direct callers for one profiled function."""

    if not isinstance(raw_callers, Mapping):
        return ()
    ranked_callers = sorted(
        raw_callers.items(),
        key=lambda item: _caller_cumulative_seconds(item[1]),
        reverse=True,
    )[:_CALLER_LIMIT]
    return tuple(
        f"{Path(key[0]).name}:{key[1]}({key[2]})="
        f"{_caller_cumulative_seconds(values) * 1_000.0:.3f}ms"
        for key, values in ranked_callers
        if isinstance(key, tuple) and len(key) == 3
    )


def _caller_cumulative_seconds(values: object) -> float:
    """Return cumulative seconds from one supported pstats caller record."""

    if isinstance(values, tuple) and len(values) >= 4:
        cumulative = values[3]
        return float(cumulative) if isinstance(cumulative, int | float) else 0.0
    return 0.0


__all__ = [
    "summarize_combined_hotspots",
    "summarize_counts",
    "summarize_hotspots",
]

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

"""Format generation execution durations for compact presentation surfaces."""

from __future__ import annotations


def format_generation_duration(duration_ms: float | int | None) -> str:
    """Return compact generation duration text for queue rows and tooltips."""

    if duration_ms is None:
        return ""
    duration = float(duration_ms)
    if duration < 0:
        return ""
    total_seconds = duration / 1000.0
    if total_seconds < 60.0:
        rounded = round(total_seconds, 1)
        if rounded.is_integer():
            return f"{int(rounded)}s"
        return f"{rounded:.1f}s"
    whole_seconds = int(total_seconds + 0.5)
    minutes, seconds = divmod(whole_seconds, 60)
    if minutes < 60:
        return f"{minutes}m{seconds}s"
    hours, remaining_minutes = divmod(minutes, 60)
    return f"{hours}h{remaining_minutes}m"


__all__ = ["format_generation_duration"]

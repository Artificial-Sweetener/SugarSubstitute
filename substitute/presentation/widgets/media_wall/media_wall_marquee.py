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

"""Resolve media wall title marquee phases without Qt dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TitleMarqueePhase = Literal["start", "scroll", "end"]


@dataclass(frozen=True, slots=True)
class TitleMarqueeState:
    """Describe how an active overflowing title should be drawn."""

    phase: TitleMarqueePhase
    offset: float = 0.0
    show_left_fade: bool = False
    show_right_fade: bool = False


def resolve_title_marquee_state(
    *,
    elapsed_ms: int,
    overflow_width: float,
    start_hold_ms: int = 900,
    end_hold_ms: int = 700,
    speed_pixels_per_second: float = 44.0,
) -> TitleMarqueeState:
    """Return the current marquee state for an overflowing active title."""

    safe_overflow = max(0.0, overflow_width)
    if safe_overflow <= 0.0:
        return TitleMarqueeState(phase="start")
    safe_speed = max(1.0, speed_pixels_per_second)
    scroll_duration_ms = max(1, round((safe_overflow / safe_speed) * 1000.0))
    cycle_duration_ms = start_hold_ms + scroll_duration_ms + end_hold_ms
    position_ms = elapsed_ms % cycle_duration_ms
    if position_ms < start_hold_ms:
        return TitleMarqueeState(
            phase="start",
            offset=0.0,
            show_right_fade=True,
        )
    scroll_position_ms = position_ms - start_hold_ms
    if scroll_position_ms < scroll_duration_ms:
        progress = scroll_position_ms / scroll_duration_ms
        offset = safe_overflow * progress
        return TitleMarqueeState(
            phase="scroll",
            offset=offset,
            show_left_fade=offset > 0.5,
            show_right_fade=offset < safe_overflow - 0.5,
        )
    return TitleMarqueeState(
        phase="end",
        offset=safe_overflow,
        show_left_fade=True,
    )


__all__ = ["TitleMarqueeState", "resolve_title_marquee_state"]

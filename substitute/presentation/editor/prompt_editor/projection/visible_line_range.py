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

"""Locate the projection lines intersecting one document-space viewport."""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Sequence
from dataclasses import dataclass, field

from .snapshot import PromptProjectionLineSnapshot


@dataclass(frozen=True, slots=True)
class PromptProjectionSourceLineIndex:
    """Locate source-intersecting visual lines without rescanning a viewport."""

    lines: tuple[PromptProjectionLineSnapshot, ...]
    _source_ends: tuple[int, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Index monotonic visual-line source ends for bounded lookup."""

        object.__setattr__(
            self,
            "_source_ends",
            tuple(line.source_end for line in self.lines),
        )

    def lines_intersecting(
        self,
        source_start: int,
        source_end: int,
    ) -> tuple[PromptProjectionLineSnapshot, ...]:
        """Return only visual lines that own part of one source range."""

        range_start = max(0, min(source_start, source_end))
        range_end = max(0, max(source_start, source_end))
        first_index = bisect_left(self._source_ends, range_start)
        matching: list[PromptProjectionLineSnapshot] = []
        for line in self.lines[first_index:]:
            if range_start == range_end:
                if line.source_start > range_start:
                    break
            elif line.source_start >= range_end:
                break
            if source_range_intersects_visual_line(
                source_start=range_start,
                source_end=range_end,
                visual_start=line.source_start,
                visual_end=line.source_end,
            ):
                matching.append(line)
        return tuple(matching)


def visible_projection_lines(
    lines: Sequence[PromptProjectionLineSnapshot],
    *,
    document_top: float,
    document_bottom: float,
) -> tuple[PromptProjectionLineSnapshot, ...]:
    """Return only lines intersecting a bounded vertical document range."""

    first_index = _first_line_ending_after(lines, document_top)
    visible: list[PromptProjectionLineSnapshot] = []
    for index in range(first_index, len(lines)):
        line = lines[index]
        if line.top > document_bottom:
            break
        visible.append(line)
    return tuple(visible)


def _first_line_ending_after(
    lines: Sequence[PromptProjectionLineSnapshot],
    document_top: float,
) -> int:
    """Return the first line whose bottom edge reaches the range top."""

    low = 0
    high = len(lines)
    while low < high:
        middle = (low + high) // 2
        line = lines[middle]
        if line.top + line.height < document_top:
            low = middle + 1
        else:
            high = middle
    return low


def source_range_intersects_visual_line(
    *,
    source_start: int,
    source_end: int,
    visual_start: int,
    visual_end: int,
) -> bool:
    """Return whether one source range owns any part of a visual line."""

    if source_start == source_end:
        return visual_start <= source_start <= visual_end
    if visual_start == visual_end:
        return source_start <= visual_start < source_end
    return visual_start < source_end and source_start < visual_end


__all__ = [
    "PromptProjectionSourceLineIndex",
    "source_range_intersects_visual_line",
    "visible_projection_lines",
]

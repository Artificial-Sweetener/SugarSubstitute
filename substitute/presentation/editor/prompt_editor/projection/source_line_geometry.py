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

"""Resolve logical source-line geometry in one pass over projection lines."""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass, field

from PySide6.QtCore import QRectF

from .selection_geometry import PromptProjectionSourceLineRect
from .snapshot import PromptProjectionLineSnapshot


@dataclass(frozen=True, slots=True)
class PromptSourceLineGeometryKey:
    """Identify one viewport-local logical source-line geometry result."""

    layout_identity: int
    viewport_left: float
    viewport_top: float
    viewport_width: float
    viewport_height: float
    scroll_offset: float
    layout_width: float


@dataclass(slots=True)
class PromptSourceLineGeometry:
    """Own exact source-line geometry reuse across frame paint consumers."""

    _cache_key: PromptSourceLineGeometryKey | None = field(init=False, default=None)
    _cache: tuple[PromptProjectionSourceLineRect, ...] = field(
        init=False,
        default=(),
    )

    def visible_rects(
        self,
        source_text: str,
        lines: Sequence[PromptProjectionLineSnapshot],
        *,
        layout_identity: int,
        viewport_rect: QRectF,
        scroll_offset: float,
        layout_width: float,
    ) -> tuple[PromptProjectionSourceLineRect, ...]:
        """Return exact-cached logical rows for one layout and viewport state."""

        key = PromptSourceLineGeometryKey(
            layout_identity=layout_identity,
            viewport_left=viewport_rect.left(),
            viewport_top=viewport_rect.top(),
            viewport_width=viewport_rect.width(),
            viewport_height=viewport_rect.height(),
            scroll_offset=scroll_offset,
            layout_width=layout_width,
        )
        if key == self._cache_key:
            return self._cache
        rects = visible_source_line_rects(
            source_text,
            lines,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
            layout_width=layout_width,
        )
        self._cache_key = key
        self._cache = rects
        return rects


def source_line_ranges(source_text: str) -> tuple[tuple[int, int], ...]:
    """Return newline-delimited source ranges including trailing empty lines."""

    ranges: list[tuple[int, int]] = []
    line_start = 0
    for index, character in enumerate(source_text):
        if character != "\n":
            continue
        ranges.append((line_start, index + 1))
        line_start = index + 1
    ranges.append((line_start, len(source_text)))
    return tuple(ranges)


def visible_source_line_rects(
    source_text: str,
    lines: Sequence[PromptProjectionLineSnapshot],
    *,
    viewport_rect: QRectF,
    scroll_offset: float,
    layout_width: float,
) -> tuple[PromptProjectionSourceLineRect, ...]:
    """Return visible logical-line rects after one projection-line traversal."""

    line_starts = _source_line_starts(source_text)
    bounds_by_source_line: dict[int, tuple[float, float]] = {}
    for line in lines:
        line_index = max(0, bisect_right(line_starts, line.source_start) - 1)
        line_bottom = line.top + line.height
        previous_bounds = bounds_by_source_line.get(line_index)
        if previous_bounds is None:
            bounds_by_source_line[line_index] = (line.top, line_bottom)
            continue
        bounds_by_source_line[line_index] = (
            min(previous_bounds[0], line.top),
            max(previous_bounds[1], line_bottom),
        )

    visible_rects: list[PromptProjectionSourceLineRect] = []
    for line_index, (top, bottom) in bounds_by_source_line.items():
        viewport_line_rect = QRectF(
            viewport_rect.left(),
            top - scroll_offset,
            max(viewport_rect.width(), layout_width),
            max(1.0, bottom - top),
        )
        if viewport_line_rect.intersects(viewport_rect):
            visible_rects.append(
                PromptProjectionSourceLineRect(
                    line_index=line_index,
                    rect=viewport_line_rect,
                )
            )
    return tuple(visible_rects)


def _source_line_starts(source_text: str) -> tuple[int, ...]:
    """Return sorted source offsets that begin logical lines."""

    return (0,) + tuple(
        index + 1 for index, character in enumerate(source_text) if character == "\n"
    )


__all__ = [
    "PromptSourceLineGeometry",
    "PromptSourceLineGeometryKey",
    "source_line_ranges",
    "visible_source_line_rects",
]

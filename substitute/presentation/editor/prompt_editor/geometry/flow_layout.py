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

"""Lay out and hit-test wrapped prompt overlay items."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QPoint, QRect, QSize


def flow_layout_rects(
    item_sizes: Sequence[QSize],
    *,
    content_rect: QRect,
    horizontal_spacing: int,
    vertical_spacing: int | None = None,
) -> tuple[QRect, ...]:
    """Lay out wrapped item rectangles inside a content rectangle."""

    if not item_sizes:
        return ()

    spacing_y = horizontal_spacing if vertical_spacing is None else vertical_spacing
    line_left = content_rect.left()
    line_top = content_rect.top()
    line_height = 0
    right_edge = content_rect.left() + max(1, content_rect.width())
    max_item_width = max(1, content_rect.width())
    rects: list[QRect] = []

    for size in item_sizes:
        width = min(max_item_width, max(1, size.width()))
        height = max(1, size.height())
        if line_height > 0 and (line_left + width) > right_edge:
            line_left = content_rect.left()
            line_top += line_height + spacing_y
            line_height = 0

        rects.append(QRect(line_left, line_top, width, height))
        line_left += width + horizontal_spacing
        line_height = max(line_height, height)

    return tuple(rects)


def flow_layout_insertion_index(
    item_rects: Sequence[QRect],
    *,
    point: QPoint,
) -> int:
    """Return the wrapped-flow insertion index nearest a point."""

    if not item_rects:
        return 0

    rows: list[list[tuple[int, QRect]]] = []
    for index, rect in enumerate(item_rects):
        if not rows or rows[-1][0][1].top() != rect.top():
            rows.append([])
        rows[-1].append((index, rect))

    target_row = min(
        rows,
        key=lambda row: abs(row[0][1].center().y() - point.y()),
    )
    for item_index, rect in target_row:
        if point.x() <= rect.center().x():
            return item_index
    return target_row[-1][0] + 1

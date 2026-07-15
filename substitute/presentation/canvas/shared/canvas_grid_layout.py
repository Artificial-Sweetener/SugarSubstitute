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

"""Construct row-major uniform-cell canvas grid geometry."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF


@dataclass(frozen=True, slots=True)
class CanvasGridLayout:
    """Describe row-major uniform-cell canvas grid geometry."""

    columns: int
    rows: int
    bounds: QRectF
    placements: tuple[QRectF, ...]


def grid_layout_for_dimensions(
    *,
    tile_count: int,
    tile_width: float,
    tile_height: float,
    gutter: float,
    columns: int,
    rows: int,
) -> CanvasGridLayout:
    """Construct geometry for an already selected valid grid shape."""

    bounds_width = columns * tile_width + max(0, columns - 1) * gutter
    bounds_height = rows * tile_height + max(0, rows - 1) * gutter
    placements: list[QRectF] = []
    for index in range(tile_count):
        row = index // columns
        column = index % columns
        tiles_in_row = min(columns, tile_count - row * columns)
        row_width = tiles_in_row * tile_width + max(0, tiles_in_row - 1) * gutter
        x_offset = (bounds_width - row_width) / 2.0
        placements.append(
            QRectF(
                x_offset + column * (tile_width + gutter),
                row * (tile_height + gutter),
                tile_width,
                tile_height,
            )
        )
    return CanvasGridLayout(
        columns=columns,
        rows=rows,
        bounds=QRectF(0.0, 0.0, bounds_width, bounds_height),
        placements=tuple(placements),
    )


__all__ = ["CanvasGridLayout", "grid_layout_for_dimensions"]

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

"""Verify uniform-cell canvas grid placement geometry."""

from __future__ import annotations

from substitute.presentation.canvas.shared.canvas_grid_layout import (
    grid_layout_for_dimensions,
)


def test_geometry_constructs_requested_row_major_shape() -> None:
    """Selected dimensions should produce stable row-major cell placement."""

    layout = grid_layout_for_dimensions(
        tile_count=6,
        tile_width=100.0,
        tile_height=50.0,
        gutter=4.0,
        columns=3,
        rows=2,
    )

    assert (layout.columns, layout.rows) == (3, 2)
    assert layout.bounds.width() == 308.0
    assert layout.bounds.height() == 104.0
    assert [(cell.x(), cell.y()) for cell in layout.placements] == [
        (0.0, 0.0),
        (104.0, 0.0),
        (208.0, 0.0),
        (0.0, 54.0),
        (104.0, 54.0),
        (208.0, 54.0),
    ]


def test_geometry_centers_incomplete_final_row() -> None:
    """An incomplete final row should remain centered in full scene bounds."""

    layout = grid_layout_for_dimensions(
        tile_count=5,
        tile_width=100.0,
        tile_height=50.0,
        gutter=4.0,
        columns=3,
        rows=2,
    )

    assert layout.placements[3].x() == 52.0
    assert layout.placements[4].x() == 156.0


def test_geometry_keeps_uniform_cells_for_single_incomplete_row() -> None:
    """Cell extents should remain uniform regardless of row occupancy."""

    layout = grid_layout_for_dimensions(
        tile_count=2,
        tile_width=80.0,
        tile_height=120.0,
        gutter=2.0,
        columns=3,
        rows=1,
    )

    assert all(cell.width() == 80.0 for cell in layout.placements)
    assert all(cell.height() == 120.0 for cell in layout.placements)
    assert layout.placements[0].x() == 41.0

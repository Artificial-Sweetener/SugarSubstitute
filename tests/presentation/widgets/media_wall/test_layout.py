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

"""Verify pure justified media wall layout policy."""

from __future__ import annotations

from substitute.presentation.widgets.media_wall import (
    JustifiedLayoutInput,
    JustifiedLayoutItem,
    build_justified_rows,
    normalize_aspect_ratio,
)


def test_justified_layout_fills_non_final_rows() -> None:
    """Fill every non-final justified row to the container width."""

    rows = build_justified_rows(
        JustifiedLayoutInput(
            items=tuple(
                JustifiedLayoutItem(
                    aspect_ratio=1.0 + (index % 3) * 0.25,
                    payload=index,
                )
                for index in range(16)
            ),
            container_width=420,
            target_row_height=110,
            min_row_height=90,
            max_row_height=130,
            gutter=4,
            minimum_tile_width=80,
        )
    )

    assert len(rows) > 1
    for row in rows[:-1]:
        occupied = sum(item.width for item in row.items) + (len(row.items) - 1) * 4
        assert round(occupied) == 420


def test_justified_layout_allows_ragged_final_row() -> None:
    """Allow the final row to remain narrower than its container."""

    rows = build_justified_rows(
        JustifiedLayoutInput(
            items=tuple(
                JustifiedLayoutItem(aspect_ratio=0.7, payload=index)
                for index in range(5)
            ),
            container_width=500,
            target_row_height=120,
            min_row_height=100,
            max_row_height=140,
            gutter=4,
            minimum_tile_width=90,
        )
    )

    final_row = rows[-1]
    occupied = (
        sum(item.width for item in final_row.items) + (len(final_row.items) - 1) * 4
    )
    assert occupied <= 500


def test_normalize_aspect_ratio_handles_invalid_values() -> None:
    """Fall back safely for non-positive aspect ratios."""

    assert normalize_aspect_ratio(0) == 0.72
    assert normalize_aspect_ratio(-1) == 0.72

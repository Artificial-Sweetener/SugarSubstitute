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

"""Contract tests for output-canvas navigation geometry helpers."""

from __future__ import annotations

from substitute.presentation.canvas.shared.output_nav_layout import (
    OutputNavControlWidths,
    compare_navigation_geometry,
    navigation_bar_width,
)


def test_navigation_bar_width_uses_visible_controls_gap_and_padding() -> None:
    """Navigation width should ignore hidden controls and include chrome padding."""

    assert (
        navigation_bar_width(
            OutputNavControlWidths(scene=60, set=34, source=0),
            gap=4,
            extra_pad=4,
        )
        == 106
    )


def test_compare_navigation_geometry_anchors_when_roomy() -> None:
    """Compare bars should anchor to lower corners when they fit horizontally."""

    geometry = compare_navigation_geometry(
        canvas_width=800,
        canvas_height=600,
        base_width=240,
        comparison_width=260,
        bar_height=36,
        padding_left=8,
        padding_right=8,
        padding_bottom=8,
        min_gap=12,
    )

    assert geometry.base.x == 8
    assert geometry.base.y == 556
    assert geometry.base.stacked is False
    assert geometry.comparison.x == 532
    assert geometry.comparison.y == 556
    assert geometry.comparison.stacked is False


def test_compare_navigation_geometry_stacks_when_bars_collide() -> None:
    """Compare bars should stack with the base bar above when space is tight."""

    geometry = compare_navigation_geometry(
        canvas_width=420,
        canvas_height=300,
        base_width=260,
        comparison_width=260,
        bar_height=36,
        padding_left=8,
        padding_right=8,
        padding_bottom=8,
        min_gap=6,
    )

    assert geometry.base.stacked is True
    assert geometry.comparison.stacked is True
    assert geometry.base.x == 8
    assert geometry.comparison.x == 8
    assert geometry.base.y == 214
    assert geometry.comparison.y == 256

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

"""Compute floating output-canvas navigation bar geometry."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OutputNavControlWidths:
    """Record measured control widths for one output navigation bar."""

    scene: int = 0
    set: int = 0
    source: int = 0


@dataclass(frozen=True)
class OutputNavBarGeometry:
    """Describe one floating output navigation bar placement."""

    x: int
    y: int
    width: int
    height: int
    stacked: bool


@dataclass(frozen=True)
class OutputCompareNavGeometry:
    """Describe base and comparison navigation bar placements."""

    base: OutputNavBarGeometry
    comparison: OutputNavBarGeometry


def navigation_bar_width(
    widths: OutputNavControlWidths,
    *,
    gap: int,
    extra_pad: int,
) -> int:
    """Return floating navigation background width for visible controls."""

    visible_widths = [
        width for width in (widths.scene, widths.set, widths.source) if width > 0
    ]
    width = sum(visible_widths)
    width += max(0, len(visible_widths) - 1) * max(0, gap)
    width += 2 * max(0, extra_pad)
    return max(width, 1)


def compare_navigation_geometry(
    *,
    canvas_width: int,
    canvas_height: int,
    base_width: int,
    comparison_width: int,
    bar_height: int,
    padding_left: int,
    padding_right: int,
    padding_bottom: int,
    min_gap: int,
) -> OutputCompareNavGeometry:
    """Return lower-corner or stacked compare navigation geometry."""

    safe_canvas_width = max(1, canvas_width)
    safe_canvas_height = max(1, canvas_height)
    safe_base_width = max(1, base_width)
    safe_comparison_width = max(1, comparison_width)
    safe_bar_height = max(1, bar_height)
    safe_padding_left = max(0, padding_left)
    safe_padding_right = max(0, padding_right)
    safe_padding_bottom = max(0, padding_bottom)
    safe_min_gap = max(0, min_gap)
    available_width = max(
        1,
        safe_canvas_width - safe_padding_left - safe_padding_right,
    )
    room_for_corners = (
        safe_base_width + safe_comparison_width + safe_min_gap <= available_width
    )
    if room_for_corners:
        y = safe_canvas_height - safe_bar_height - safe_padding_bottom
        return OutputCompareNavGeometry(
            base=OutputNavBarGeometry(
                x=safe_padding_left,
                y=y,
                width=safe_base_width,
                height=safe_bar_height,
                stacked=False,
            ),
            comparison=OutputNavBarGeometry(
                x=max(
                    safe_padding_left,
                    safe_canvas_width - safe_padding_right - safe_comparison_width,
                ),
                y=y,
                width=safe_comparison_width,
                height=safe_bar_height,
                stacked=False,
            ),
        )
    comparison_y = safe_canvas_height - safe_bar_height - safe_padding_bottom
    base_y = comparison_y - safe_bar_height - safe_min_gap
    return OutputCompareNavGeometry(
        base=OutputNavBarGeometry(
            x=safe_padding_left,
            y=max(0, base_y),
            width=min(safe_base_width, available_width),
            height=safe_bar_height,
            stacked=True,
        ),
        comparison=OutputNavBarGeometry(
            x=safe_padding_left,
            y=max(0, comparison_y),
            width=min(safe_comparison_width, available_width),
            height=safe_bar_height,
            stacked=True,
        ),
    )


__all__ = [
    "OutputCompareNavGeometry",
    "OutputNavBarGeometry",
    "OutputNavControlWidths",
    "compare_navigation_geometry",
    "navigation_bar_width",
]

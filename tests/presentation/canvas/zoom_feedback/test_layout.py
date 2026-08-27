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

"""Test zoom-feedback labels and comparison badge layout."""

from __future__ import annotations

from PySide6.QtCore import QLineF, QPointF, QRect, QRectF
from cutecanvas import CanvasComparisonDivider, ComparisonOrientation
import pytest

from substitute.presentation.canvas.shared.canvas_zoom_indicator import (
    CanvasZoomScale,
)
from substitute.presentation.canvas.shared.canvas_zoom_indicator_layout import (
    CanvasZoomBadge,
    position_zoom_badges,
)


def test_zoom_scale_formats_uniform_and_anisotropic_percentages() -> None:
    """Keep scale labels compact without concealing unequal source axes."""

    assert CanvasZoomScale(1.25, 1.25).label() == "125%"
    assert CanvasZoomScale(0.063, 0.063).label() == "6.3%"
    assert CanvasZoomScale(2.0, 1.0).label() == "200% × 100%"


@pytest.mark.parametrize(
    ("position", "expected_texts"),
    (
        (QPointF(100.0, 150.0), ("125%", "83%")),
        (QPointF(600.0, 150.0), ("125%", "83%")),
        (QPointF(399.0, 590.0), ("125%", "83%")),
    ),
)
def test_comparison_badges_stay_in_their_reveal_regions(
    position: QPointF,
    expected_texts: tuple[str, str],
) -> None:
    """Clamp active and passive labels under cursor, divider, and edge pressure."""

    badges = position_zoom_badges(
        QRect(0, 0, 800, 600),
        position,
        _vertical_divider(),
        _badge("125%", width=80.0),
        _badge("83%", width=70.0),
    )

    assert tuple(badge.text for badge in badges) == expected_texts
    assert badges[0].bounds.right() <= 394.0
    assert badges[1].bounds.left() >= 406.0
    assert badges[0].bounds.top() == badges[1].bounds.top()
    assert all(
        QRectF(0.0, 0.0, 800.0, 600.0).contains(badge.bounds) for badge in badges
    )


@pytest.mark.parametrize(
    ("divider_x", "expected_text"),
    ((900.0, "125%"), (-100.0, "83%")),
)
def test_offscreen_comparison_side_keeps_the_visible_badge(
    divider_x: float,
    expected_text: str,
) -> None:
    """Retain the visible label when the other reveal is offscreen."""

    divider = CanvasComparisonDivider(
        enabled=True,
        split_position=0.5,
        orientation=ComparisonOrientation.VERTICAL,
        visible_segment=None,
        full_segment=QLineF(divider_x, 0.0, divider_x, 600.0),
    )

    badges = position_zoom_badges(
        QRect(0, 0, 800, 600),
        QPointF(300.0, 200.0),
        divider,
        _badge("125%", width=60.0),
        _badge("83%", width=54.0),
    )

    assert tuple(badge.text for badge in badges) == (expected_text,)
    assert badges[0].bounds.topLeft() == QPointF(312.0, 212.0)


def _badge(text: str, *, width: float) -> CanvasZoomBadge:
    """Return deterministic badge geometry."""

    return CanvasZoomBadge(text, QRectF(0.0, 0.0, width, 28.0))


def _vertical_divider() -> CanvasComparisonDivider:
    """Return a centered vertical comparison divider."""

    segment = QLineF(400.0, 0.0, 400.0, 600.0)
    return CanvasComparisonDivider(
        enabled=True,
        split_position=0.5,
        orientation=ComparisonOrientation.VERTICAL,
        visible_segment=segment,
        full_segment=segment,
    )

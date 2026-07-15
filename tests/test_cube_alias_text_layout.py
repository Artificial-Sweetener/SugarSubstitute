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

"""Tests for shared cube alias text layout."""

from __future__ import annotations

from math import ceil

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFont, QImage, QPainter
from PySide6.QtWidgets import QApplication

from substitute.presentation.cubes.cube_alias_text_layout import (
    cube_alias_prefix_font,
    cube_alias_primary_baseline_y,
    layout_cube_alias_text,
    split_cube_alias_prefix,
)
from substitute.presentation.cubes.cube_card_visual import CubeCardVisual
from substitute.presentation.cubes.cube_stack_metrics import (
    CUBE_ITEM_EXPANDED_WIDTH,
    CUBE_ITEM_HEIGHT,
)


def _app() -> QApplication:
    """Return a QApplication for font metric access."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


def _painter() -> tuple[QImage, QPainter]:
    """Return an active offscreen painter and its backing image."""

    image = QImage(240, 80, QImage.Format.Format_ARGB32)
    return image, QPainter(image)


def test_split_cube_alias_prefix_splits_leading_slash_prefix() -> None:
    """A leading non-empty slash segment should become the prefix token."""

    parts = split_cube_alias_prefix("SDXL/Text to Image")

    assert parts.prefix == "SDXL/"
    assert parts.body == "Text to Image"


def test_split_cube_alias_prefix_ignores_missing_or_boundary_slashes() -> None:
    """Prefix splitting requires non-empty text before and after the slash."""

    assert split_cube_alias_prefix("Text to Image").prefix == ""
    assert split_cube_alias_prefix("/Text to Image").prefix == ""
    assert split_cube_alias_prefix("SDXL/").prefix == ""


def test_cube_alias_prefix_font_uses_reduced_primary_point_size() -> None:
    """The prefix font should use 60 percent of primary point size."""

    font = QFont()
    font.setPointSize(14)

    prefix_font = cube_alias_prefix_font(font)

    assert prefix_font.pointSizeF() == 8.4


def test_cube_alias_primary_baseline_uses_primary_font_metrics() -> None:
    """Prefix and body should share the primary body baseline."""

    _app()
    image, painter = _painter()
    font = QFont()
    font.setPointSize(14)
    rect = QRectF(12, 4, 120, 20)

    baseline_y = cube_alias_primary_baseline_y(
        painter,
        row_rect=rect,
        primary_font=font,
    )
    painter.setFont(font)
    metrics = painter.fontMetrics()
    expected_y = rect.y() + ((rect.height() - metrics.height()) / 2)
    expected_y += metrics.ascent()
    painter.end()

    assert baseline_y == expected_y
    assert not image.isNull()


def test_layout_cube_alias_text_caps_prefix_and_allocates_body_width() -> None:
    """Long prefixes should not consume more than 45 percent of the row."""

    _app()
    image, painter = _painter()
    font = QFont()
    font.setPointSize(14)
    rect = QRectF(0, 0, 100, 20)

    layout = layout_cube_alias_text(
        painter,
        text="VeryLongModelPrefix/Text",
        row_rect=rect,
        primary_font=font,
    )
    painter.end()

    assert layout.prefix_segment is not None
    assert layout.prefix_segment.rect.width() <= 45.0
    assert layout.body_segment.rect.x() == layout.prefix_segment.rect.right()
    assert layout.body_segment.rect.width() >= 55.0
    assert layout.prefix_segment.baseline_y == layout.body_segment.baseline_y
    assert not image.isNull()


def test_layout_cube_alias_text_preserves_short_prefix_without_elision() -> None:
    """Allocate enough width for a short prefix to render in full."""

    _app()
    image, painter = _painter()
    font = QFont()
    font.setPointSize(14)
    text_rect = CubeCardVisual.text_rect_for_width(
        CUBE_ITEM_EXPANDED_WIDTH,
        CUBE_ITEM_HEIGHT,
        has_icon=True,
        close_visible=True,
        compact_progress=0.0,
    )
    primary_rect, _secondary_rect = CubeCardVisual.text_row_rects(text_rect)
    layout = layout_cube_alias_text(
        painter,
        text="SDXL/Text to Image",
        row_rect=primary_rect,
        primary_font=font,
    )

    prefix = layout.prefix_segment
    assert prefix is not None
    painter.setFont(prefix.font)
    rendered_prefix = painter.fontMetrics().elidedText(
        prefix.text,
        Qt.TextElideMode.ElideRight,
        ceil(prefix.rect.width()),
    )
    painter.end()

    assert rendered_prefix == "SDXL/"
    assert not image.isNull()

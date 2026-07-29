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

"""Own the shared Fluent vertical selection-indicator visual."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget
from qfluentwidgets.common.color import themeColor  # type: ignore[import-untyped]

FLUENT_VERTICAL_INDICATOR_HEIGHT = 16
FLUENT_VERTICAL_INDICATOR_WIDTH = 3


def centered_vertical_indicator_y(widget: QWidget) -> int:
    """Return the top coordinate that centers the shared marker on a widget."""

    return widget.y() + widget.height() // 2 - FLUENT_VERTICAL_INDICATOR_HEIGHT // 2


def paint_fluent_vertical_indicator(
    painter: QPainter,
    *,
    x: int,
    y: int,
    height: int = FLUENT_VERTICAL_INDICATOR_HEIGHT,
) -> None:
    """Paint the product's Fluent accent marker at one owner-provided position."""

    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(themeColor())
    painter.drawRoundedRect(
        x,
        y,
        FLUENT_VERTICAL_INDICATOR_WIDTH,
        height,
        1.5,
        1.5,
    )


__all__ = [
    "FLUENT_VERTICAL_INDICATOR_HEIGHT",
    "FLUENT_VERTICAL_INDICATOR_WIDTH",
    "centered_vertical_indicator_y",
    "paint_fluent_vertical_indicator",
]

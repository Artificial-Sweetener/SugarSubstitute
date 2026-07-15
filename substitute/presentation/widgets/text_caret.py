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

"""Share text caret geometry, painting, and blink timing across custom widgets."""

from __future__ import annotations

from PySide6.QtCore import QRect, QRectF
from PySide6.QtGui import QPainter, QPalette
from PySide6.QtWidgets import QApplication

TEXT_CARET_WIDTH = 1.0
TEXT_CARET_REPAINT_MARGIN = 1


def text_caret_rect(source_rect: QRect | QRectF) -> QRectF:
    """Return a prompt-editor-style 1 px caret centered in a source cursor rect."""

    rect = QRectF(source_rect)
    left = rect.center().x() - (TEXT_CARET_WIDTH / 2.0)
    return QRectF(left, rect.top(), TEXT_CARET_WIDTH, max(1.0, rect.height()))


def text_caret_repaint_rect(source_rect: QRect | QRectF) -> QRect:
    """Return the widget update rect needed for one normalized text caret."""

    margin = TEXT_CARET_REPAINT_MARGIN
    return (
        text_caret_rect(source_rect)
        .toAlignedRect()
        .adjusted(
            -margin,
            -margin,
            margin,
            margin,
        )
    )


def paint_text_caret(
    painter: QPainter,
    source_rect: QRect | QRectF,
    palette: QPalette,
) -> None:
    """Paint a prompt-editor-style text caret using the widget text color."""

    painter.fillRect(
        text_caret_rect(source_rect),
        palette.color(QPalette.ColorRole.Text),
    )


def text_caret_blink_interval_ms(flash_time_ms: int) -> int:
    """Return the visible/hidden timer interval for one application flash period."""

    if flash_time_ms <= 0:
        return 0
    return max(1, flash_time_ms // 2)


def application_text_caret_blink_interval_ms() -> int:
    """Return the text caret blink interval from the current Qt application setting."""

    return text_caret_blink_interval_ms(int(QApplication.cursorFlashTime()))


def is_application_text_caret_blink_enabled() -> bool:
    """Return whether Qt application settings allow text caret blinking."""

    return int(QApplication.cursorFlashTime()) > 0


__all__ = [
    "TEXT_CARET_REPAINT_MARGIN",
    "TEXT_CARET_WIDTH",
    "application_text_caret_blink_interval_ms",
    "is_application_text_caret_blink_enabled",
    "paint_text_caret",
    "text_caret_blink_interval_ms",
    "text_caret_rect",
    "text_caret_repaint_rect",
]

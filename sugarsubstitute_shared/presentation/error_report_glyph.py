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

"""Render and align the severity glyph used by error-report dialogs."""

from __future__ import annotations

from enum import Enum
from typing import cast

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter, QPaintEvent
from PySide6.QtWidgets import QLabel, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    InfoBarIcon,
    Theme,
    drawIcon,
)

_HEADER_TEXT_SPACING = 4


class ReportSeverity(Enum):
    """Classify the shared report glyph and presentation tone."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ReportSeverityGlyphWidget(QWidget):
    """Draw qfluent's WinUI severity glyph without an InfoBar surface."""

    def __init__(
        self,
        *,
        size: int,
        severity: ReportSeverity,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the fixed-size modal header glyph."""

        super().__init__(parent)
        self._glyph_size = size
        self._severity = severity
        self.setFixedSize(size, size)

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        """Paint the qfluent glyph that matches the report severity."""

        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
        )
        drawIcon(
            _severity_icon(self._severity),
            painter,
            QRectF(0, 0, self._glyph_size, self._glyph_size),
            theme=Theme.LIGHT,
        )

    def icon_path(self) -> str:
        """Return the qfluent asset used by the modal header."""

        return cast("str", _severity_icon(self._severity).path(Theme.LIGHT))


def header_glyph_size(title: QLabel, message: QLabel) -> int:
    """Return an error glyph size matching the visible two-row text bounds."""

    ink_top, ink_bottom = _header_text_ink_bounds(title, message)
    return max(16, ink_bottom - ink_top - 1)


def header_icon_top_offset(title: QLabel, message: QLabel, icon_size: int) -> int:
    """Return the icon top offset inside the two-row grid-spanning cell."""

    title_top = 0
    message_bottom = (
        title.fontMetrics().height() + _HEADER_TEXT_SPACING + message.height()
    )
    cell_center = (title_top + message_bottom) / 2
    ink_top, ink_bottom = _header_text_ink_bounds(title, message)
    ink_center = (ink_top + ink_bottom) / 2
    centered_top = round(cell_center - (icon_size / 2))
    return max(0, centered_top + int(ink_center - cell_center))


def _severity_icon(severity: ReportSeverity) -> InfoBarIcon:
    """Return the qfluent severity icon for one report."""

    if severity is ReportSeverity.WARNING:
        return InfoBarIcon.WARNING
    if severity is ReportSeverity.INFO:
        return InfoBarIcon.INFORMATION
    return InfoBarIcon.ERROR


def _header_text_ink_bounds(title: QLabel, message: QLabel) -> tuple[int, int]:
    """Return the visible text bounds of the two-line header stack."""

    title_ink_top, title_ink_bottom = _label_ink_bounds(title, 0)
    message_top = title.fontMetrics().height() + _HEADER_TEXT_SPACING
    message_ink_top, message_ink_bottom = _label_ink_bounds(message, message_top)
    return min(title_ink_top, message_ink_top), max(
        title_ink_bottom,
        message_ink_bottom,
    )


def _label_ink_bounds(label: QLabel, top: int) -> tuple[int, int]:
    """Return vertical text ink bounds relative to the header origin."""

    metrics = label.fontMetrics()
    rect = metrics.tightBoundingRect(label.text() or " ")
    ink_top = top + metrics.ascent() + rect.top()
    return ink_top, ink_top + rect.height()


__all__ = [
    "ReportSeverityGlyphWidget",
    "ReportSeverity",
    "header_glyph_size",
    "header_icon_top_offset",
]

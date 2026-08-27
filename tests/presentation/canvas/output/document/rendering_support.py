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

"""Provide shared Output document fixtures and observations."""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import (
    QColor,
)
from PySide6.QtWidgets import QApplication, QWidget
from tests.support.qt.semantic_wait import wait_for_qt_condition


class _ZoomOverlayPainter:
    """Record Output percentage badges painted through the public overlay hook."""

    def __init__(self) -> None:
        """Initialize the recorded overlay operations."""

        self.texts: list[str] = []
        self.bounds: list[QRectF] = []
        self._opacity = 1.0

    def save(self) -> None:
        """Accept the painter save operation."""

    def restore(self) -> None:
        """Accept the painter restore operation."""

    def opacity(self) -> float:
        """Return the current painter opacity."""

        return self._opacity

    def setOpacity(self, opacity: float) -> None:  # noqa: N802
        """Record the current painter opacity."""

        self._opacity = opacity

    def setRenderHint(self, *_args: object) -> None:  # noqa: N802
        """Accept the antialiasing render hint."""

    def setFont(self, *_args: object) -> None:  # noqa: N802
        """Accept the established percentage-label font."""

    def setBrush(self, *_args: object) -> None:  # noqa: N802
        """Accept the established overlay material brush."""

    def setPen(self, *_args: object) -> None:  # noqa: N802
        """Accept the established overlay border and text pens."""

    def drawRoundedRect(self, bounds: QRectF, *_args: object) -> None:  # noqa: N802
        """Record one painted badge background."""

        self.bounds.append(QRectF(bounds))

    def drawText(self, _bounds: object, _alignment: object, text: str) -> None:  # noqa: N802
        """Record one painted percentage label."""

        self.texts.append(text)


def _wait_for_rendered_color(
    application: QApplication,
    target: QWidget,
    expected: QColor,
) -> bool:
    """Wait until an offscreen target renders the admitted image color."""

    del application

    def rendered_color_matches() -> bool:
        """Compare the current center sample with the expected color."""

        image = target.grab().toImage()
        if image.isNull():
            return False
        sampled = image.pixelColor(image.width() // 2, image.height() // 2)
        return sampled == expected

    wait_for_qt_condition(rendered_color_matches)
    return True


def _assert_rendered_horizontal_seam(
    workspace: object,
    x: int,
    seam_y: int,
    expected_gap: int,
) -> None:
    """Require the visible grid seam to contain one stable raster gap."""

    grab = getattr(workspace, "grab")
    image = grab().toImage()
    assert not image.isNull()
    upper = image.pixelColor(x, seam_y - 1)
    lower = image.pixelColor(x, seam_y + expected_gap)
    assert upper == QColor("red")
    sampled_rows = ", ".join(
        f"{row}:{image.pixelColor(x, row).name()}"
        for row in range(seam_y - 2, seam_y + expected_gap + 24)
    )
    assert lower == QColor("red"), sampled_rows
    assert all(
        image.pixelColor(x, y) != QColor("red")
        for y in range(seam_y, seam_y + expected_gap)
    )

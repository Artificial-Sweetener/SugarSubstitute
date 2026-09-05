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

"""Save readable opaque dark-theme evidence for translucent installer windows."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPalette
from PySide6.QtWidgets import QWidget

_DARK_BACKDROP = QColor("#181818")


def prepare_opaque_dark_capture_surface(widget: QWidget) -> None:
    """Replace unavailable native backdrop material for an offscreen capture."""

    widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
    palette = widget.palette()
    palette.setColor(QPalette.ColorRole.Window, _DARK_BACKDROP)
    widget.setPalette(palette)
    widget.setAutoFillBackground(True)
    widget.setStyleSheet(
        widget.styleSheet()
        + "\nQWidget#OnboardingRoot, QWidget#OnboardingSurface {"
        + " background-color: #181818; }"
    )


def save_opaque_dark_widget_capture(widget: QWidget, path: Path) -> None:
    """Composite a translucent production window onto its dark desktop backdrop."""

    pixmap = widget.grab()
    image = QImage(pixmap.size(), QImage.Format.Format_RGB32)
    image.setDevicePixelRatio(pixmap.devicePixelRatio())
    image.fill(_DARK_BACKDROP)
    painter = QPainter(image)
    painter.drawPixmap(0, 0, pixmap)
    painter.end()
    if not image.save(str(path)):
        raise RuntimeError(f"Could not write smoke screenshot: {path}")


__all__ = [
    "prepare_opaque_dark_capture_surface",
    "save_opaque_dark_widget_capture",
]

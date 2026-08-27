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

"""Provide focused contextual-toolbar motion fixtures and observations."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QPushButton,
    QWidget,
)

from substitute.presentation.canvas.shared.canvas_chrome_metrics import (
    CANVAS_CHROME_CONTROL_HEIGHT,
)
from substitute.presentation.canvas.shared.contextual_toolbar import (
    ContextualToolbarPage,
)


class MotionPage(ContextualToolbarPage):
    """Provide deterministic intrinsic width and one focusable control."""

    def __init__(self, width: int, parent: QWidget) -> None:
        """Create one canonical row with a fixed-width button."""

        super().__init__(parent)
        self.button = QPushButton("Control", self)
        self.button.setFixedSize(width, CANVAS_CHROME_CONTROL_HEIGHT)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.button)


def qt_application() -> QApplication:
    """Return the shared GUI application required by toolbar widgets."""

    instance = QCoreApplication.instance()
    return instance if isinstance(instance, QApplication) else QApplication([])


def effective_opacity(page: ContextualToolbarPage) -> float:
    """Return one page's effective host opacity for motion assertions."""

    parent = page.parentWidget()
    effect = None if parent is None else parent.graphicsEffect()
    opacity = getattr(effect, "opacity", None)
    return 1.0 if not callable(opacity) else float(opacity())


__all__ = ["MotionPage", "effective_opacity", "qt_application"]

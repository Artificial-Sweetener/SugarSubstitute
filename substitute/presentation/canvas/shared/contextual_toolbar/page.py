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

"""Define replaceable content hosted by the shared Contextual Toolbar."""

from __future__ import annotations

from PySide6.QtCore import QSize, Signal
from PySide6.QtWidgets import QWidget

from substitute.presentation.canvas.shared.canvas_chrome_metrics import (
    CANVAS_CHROME_CONTROL_HEIGHT,
    CANVAS_CHROME_GAP,
)


class ContextualToolbarPage(QWidget):
    """Publish intrinsic geometry changes from one focused toolbar context."""

    geometryChanged = Signal()
    canonical_rows = 1

    def __init__(self, parent: QWidget) -> None:
        """Create one page owned by the toolbar content host."""
        super().__init__(parent)

    def sizeHint(self) -> QSize:  # noqa: N802
        """Return intrinsic width with a canonical content-row height."""
        hint = super().sizeHint()
        row_height = CANVAS_CHROME_CONTROL_HEIGHT
        height = self.canonical_rows * row_height + (
            max(0, self.canonical_rows - 1) * CANVAS_CHROME_GAP
        )
        return QSize(hint.width(), height)


__all__ = ["ContextualToolbarPage"]

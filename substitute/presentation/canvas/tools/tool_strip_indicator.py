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

"""Paint the active marker and delegate its WinUI-style transition motion."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget

from substitute.presentation.widgets.fluent_vertical_indicator import (
    FLUENT_VERTICAL_INDICATOR_HEIGHT,
    centered_vertical_indicator_y,
    paint_fluent_vertical_indicator,
)

from .tool_strip_indicator_motion import CanvasToolIndicatorMotion


class CanvasToolStripIndicator(QWidget):
    """Render the active marker from one stretch-and-settle motion owner."""

    def __init__(self, strip: QWidget) -> None:
        """Create a pointer-transparent overlay and reusable motion sequence."""

        super().__init__(strip)
        self._indicator_y = 0
        self._indicator_height = FLUENT_VERTICAL_INDICATOR_HEIGHT
        self._target_y = 0
        self.motion = CanvasToolIndicatorMotion(
            parent=self,
            apply_frame=self._apply_frame,
        )
        self.animation = self.motion.animation
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.hide()

    @property
    def indicator_y(self) -> int:
        """Return the marker's current top coordinate."""

        return self._indicator_y

    @property
    def indicator_height(self) -> int:
        """Return the marker's current animated height."""

        return self._indicator_height

    @property
    def target_y(self) -> int:
        """Return the marker's authoritative destination coordinate."""

        return self._target_y

    def move_to(self, button: QWidget, *, animated: bool) -> None:
        """Align the marker with one active button using connected Fluent motion."""

        target_y = centered_vertical_indicator_y(button)
        self._target_y = target_y
        parent = self.parentWidget()
        if parent is None:
            return
        self.setGeometry(parent.rect())
        self.raise_()
        self.show()
        if animated and target_y != self._indicator_y:
            self.motion.start(
                from_top=self._indicator_y,
                from_height=self._indicator_height,
                target_top=target_y,
                target_height=FLUENT_VERTICAL_INDICATOR_HEIGHT,
            )
            return
        self.motion.stop()
        self._apply_frame(target_y, FLUENT_VERTICAL_INDICATOR_HEIGHT)

    def clear(self) -> None:
        """Hide the marker when the palette has no active enabled mode."""

        self.motion.stop()
        self.hide()

    def sync_geometry(self) -> None:
        """Match the strip geometry and preserve overlay z-order."""

        parent = self.parentWidget()
        if parent is None:
            return
        self.setGeometry(parent.rect())
        self.raise_()
        self.update()

    def paintEvent(self, event: object) -> None:
        """Draw the current connected marker geometry in the theme accent."""

        _ = event
        painter = QPainter(self)
        paint_fluent_vertical_indicator(
            painter,
            x=1,
            y=self._indicator_y,
            height=self._indicator_height,
        )

    def _apply_frame(self, top: int, height: int) -> None:
        """Accept one motion frame and repaint its connected geometry."""

        self._indicator_y = top
        self._indicator_height = height
        self.update()


__all__ = ["CanvasToolStripIndicator"]

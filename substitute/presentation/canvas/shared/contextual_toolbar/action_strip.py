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

"""Project runtime tool contributions into Contextual Toolbar action buttons."""

from __future__ import annotations

from PySide6.QtCore import QSize, Signal
from PySide6.QtWidgets import QHBoxLayout, QWidget

from substitute.presentation.canvas.shared.canvas_chrome_metrics import (
    CANVAS_CHROME_CONTROL_HEIGHT,
    CANVAS_CHROME_GAP,
)
from substitute.presentation.canvas.tools.model import (
    CanvasToolKind,
    CanvasToolPresentation,
    CanvasToolSurface,
)
from substitute.presentation.canvas.tools.palette import (
    CanvasToolPalette,
    CanvasToolPaletteSubscription,
)
from substitute.presentation.localization import LocalizedPushButton


class CanvasContextualToolbarActionStrip(QWidget):
    """Own stable action buttons for one runtime surface projection."""

    toolRequested = Signal(str)
    geometryChanged = Signal()

    def __init__(self, palette: CanvasToolPalette, parent: QWidget) -> None:
        """Observe the Contextual Toolbar surface of one live palette."""
        super().__init__(parent)
        self._buttons: dict[str, LocalizedPushButton] = {}
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(CANVAS_CHROME_GAP // 2)
        self._layout.setSizeConstraint(QHBoxLayout.SizeConstraint.SetFixedSize)
        self._subscription: CanvasToolPaletteSubscription = palette.subscribe(
            self._palette_changed,
            surface=CanvasToolSurface.CONTEXTUAL_TOOLBAR,
        )
        self.destroyed.connect(self._subscription.close)
        self._palette_changed(palette.snapshot(CanvasToolSurface.CONTEXTUAL_TOOLBAR))

    def button_for(self, tool_id: str) -> LocalizedPushButton | None:
        """Return one live action button by stable tool identity."""
        return self._buttons.get(tool_id)

    def _palette_changed(
        self,
        presentations: tuple[CanvasToolPresentation, ...],
    ) -> None:
        """Update state in place or rebuild only when contribution order changes."""
        identities = tuple(item.tool_id for item in presentations)
        if identities != tuple(self._buttons):
            self._replace_buttons(presentations)
        for presentation in presentations:
            button = self._buttons[presentation.tool_id]
            button.setEnabled(presentation.enabled)
            button.setChecked(
                presentation.kind is CanvasToolKind.MODE and presentation.active
            )

    def _replace_buttons(
        self,
        presentations: tuple[CanvasToolPresentation, ...],
    ) -> None:
        """Replace structural button ownership from one ordered projection."""
        for button in self._buttons.values():
            self._layout.removeWidget(button)
            button.close()
            button.deleteLater()
        self._buttons.clear()
        for presentation in presentations:
            button = LocalizedPushButton(presentation.label, self)
            button.setObjectName("ContextualToolbarActionButton")
            button.setFixedHeight(CANVAS_CHROME_CONTROL_HEIGHT)
            button.setIcon(presentation.icon)
            button.setIconSize(QSize(16, 16))
            button.setCheckable(presentation.kind is CanvasToolKind.MODE)
            button.clicked.connect(
                lambda _checked=False, tool_id=presentation.tool_id: (
                    self.toolRequested.emit(tool_id)
                )
            )
            self._layout.addWidget(button)
            self._buttons[presentation.tool_id] = button
        self._layout.activate()
        self.adjustSize()
        self.updateGeometry()
        self.geometryChanged.emit()


__all__ = ["CanvasContextualToolbarActionStrip"]

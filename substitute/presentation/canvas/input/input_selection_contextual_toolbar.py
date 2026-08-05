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

"""Present default pixel-selection actions in the shared Contextual Toolbar."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QWidget
from qfluentwidgets import FluentIcon  # type: ignore[import-untyped]

from sugarsubstitute_shared.presentation.localization import app_text
from substitute.presentation.canvas.shared.canvas_chrome_metrics import (
    CANVAS_CHROME_CONTROL_HEIGHT,
    CANVAS_CHROME_GAP,
)
from substitute.presentation.canvas.shared.contextual_toolbar import (
    CanvasContextualToolbarActionStrip,
    ContextualToolbarPage,
)
from substitute.presentation.canvas.tools import CanvasToolRuntime
from substitute.presentation.localization import LocalizedPushButton


class InputSelectionContextualToolbarPage(ContextualToolbarPage):
    """Compose selection modification entry with runtime-contributed actions."""

    modifyRequested = Signal()
    toolRequested = Signal(str)

    def __init__(
        self,
        *,
        runtime: CanvasToolRuntime,
        parent: QWidget,
    ) -> None:
        """Build the stable default selection context."""

        super().__init__(parent)
        self.modify_button = LocalizedPushButton(app_text("Modify selection"), self)
        self.modify_button.setObjectName("ContextualToolbarModifySelectionButton")
        self.modify_button.setIcon(FluentIcon.EDIT)
        self.modify_button.setFixedHeight(CANVAS_CHROME_CONTROL_HEIGHT)
        self.action_strip = CanvasContextualToolbarActionStrip(runtime.palette, self)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(CANVAS_CHROME_GAP // 2)
        layout.addWidget(self.modify_button)
        layout.addWidget(self.action_strip)

        self.modify_button.clicked.connect(self.modifyRequested.emit)
        self.action_strip.geometryChanged.connect(self._geometry_changed)
        self.action_strip.toolRequested.connect(self.toolRequested.emit)

    def _geometry_changed(self, *_args: object) -> None:
        """Publish settled page geometry after contribution changes."""

        layout = self.layout()
        if layout is not None:
            layout.activate()
        self.adjustSize()
        self.updateGeometry()
        self.geometryChanged.emit()


__all__ = ["InputSelectionContextualToolbarPage"]

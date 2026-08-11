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

"""Present localized Undo and Redo controls for provisional canvas history."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QWidget

from sugarsubstitute_shared.presentation.localization import app_text
from substitute.presentation.canvas.shared.canvas_chrome_metrics import (
    CANVAS_CHROME_GAP,
)
from substitute.presentation.resources.fluent_app_icon import AppIcon

from .command_button import ContextualToolbarCommandButton


class ContextualToolbarHistoryControls(QWidget):
    """Own compact localized Undo and Redo command presentation."""

    undoRequested = Signal()
    redoRequested = Signal()

    def __init__(self, parent: QWidget) -> None:
        """Build compact icon commands with localized accessible semantics."""

        super().__init__(parent)
        self.undo_button = ContextualToolbarCommandButton(
            AppIcon.ARROW_UNDO_20_REGULAR,
            app_text("Undo"),
            self,
        )
        self.redo_button = ContextualToolbarCommandButton(
            AppIcon.ARROW_REDO_20_REGULAR,
            app_text("Redo"),
            self,
        )
        self.undo_button.setObjectName("ContextualToolbarUndoButton")
        self.redo_button.setObjectName("ContextualToolbarRedoButton")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(CANVAS_CHROME_GAP // 2)
        layout.addWidget(self.undo_button)
        layout.addWidget(self.redo_button)

        self.undo_button.clicked.connect(self.undoRequested.emit)
        self.redo_button.clicked.connect(self.redoRequested.emit)

    def set_available(self, *, undo: bool, redo: bool) -> None:
        """Project authoritative unified-history availability."""

        self.undo_button.setEnabled(undo)
        self.redo_button.setEnabled(redo)


__all__ = ["ContextualToolbarHistoryControls"]

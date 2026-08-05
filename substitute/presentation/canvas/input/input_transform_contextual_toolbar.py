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

"""Present explicit settlement for selected-pixel affine transformation."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QWidget
from cutecanvas import EditorTransformCommand, EditorTransformTarget

from sugarsubstitute_shared.presentation.localization import app_text
from substitute.presentation.canvas.shared.canvas_chrome_metrics import (
    CANVAS_CHROME_GAP,
)
from substitute.presentation.canvas.shared.contextual_toolbar import (
    ContextualToolbarPage,
    ContextualToolbarSettlementControls,
)
from substitute.presentation.canvas.shared.contextual_toolbar.command_button import (
    ContextualToolbarCommandButton,
)
from substitute.presentation.localization import LocalizedStrongBodyLabel
from substitute.presentation.resources.fluent_app_icon import AppIcon


class InputTransformContextualToolbarPage(ContextualToolbarPage):
    """Expose Apply and Cancel for one unresolved selected-pixel transform."""

    applyRequested = Signal()
    cancelRequested = Signal()
    commandRequested = Signal(object)

    def __init__(self, target: EditorTransformTarget, parent: QWidget) -> None:
        """Build the compact transform transaction surface."""
        super().__init__(parent)
        label = (
            app_text("Transform selection")
            if target is EditorTransformTarget.SELECTION_CONTENT
            else app_text("Transform")
        )
        self.label = LocalizedStrongBodyLabel(label, self)
        self.rotate_left_button = ContextualToolbarCommandButton(
            AppIcon.ROTATE_LEFT_20_REGULAR,
            app_text("Rotate left"),
            self,
        )
        self.rotate_right_button = ContextualToolbarCommandButton(
            AppIcon.ROTATE_RIGHT_20_REGULAR,
            app_text("Rotate right"),
            self,
        )
        self.flip_horizontal_button = ContextualToolbarCommandButton(
            AppIcon.FLIP_HORIZONTAL_20_REGULAR,
            app_text("Flip horizontal"),
            self,
        )
        self.flip_vertical_button = ContextualToolbarCommandButton(
            AppIcon.FLIP_VERTICAL_20_REGULAR,
            app_text("Flip vertical"),
            self,
        )
        self.settlement_controls = ContextualToolbarSettlementControls(self)
        self.apply_button = self.settlement_controls.apply_button
        self.cancel_button = self.settlement_controls.cancel_button
        self.apply_button.setObjectName("ContextualToolbarTransformApplyButton")
        self.cancel_button.setObjectName("ContextualToolbarTransformCancelButton")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(CANVAS_CHROME_GAP // 2)
        layout.addWidget(self.label)
        layout.addWidget(self.rotate_left_button)
        layout.addWidget(self.rotate_right_button)
        layout.addWidget(self.flip_horizontal_button)
        layout.addWidget(self.flip_vertical_button)
        layout.addWidget(self.settlement_controls)

        self.settlement_controls.applyRequested.connect(self.applyRequested.emit)
        self.settlement_controls.cancelRequested.connect(self.cancelRequested.emit)
        self.rotate_left_button.clicked.connect(
            lambda: self.commandRequested.emit(EditorTransformCommand.ROTATE_LEFT_90)
        )
        self.rotate_right_button.clicked.connect(
            lambda: self.commandRequested.emit(EditorTransformCommand.ROTATE_RIGHT_90)
        )
        self.flip_horizontal_button.clicked.connect(
            lambda: self.commandRequested.emit(EditorTransformCommand.FLIP_HORIZONTAL)
        )
        self.flip_vertical_button.clicked.connect(
            lambda: self.commandRequested.emit(EditorTransformCommand.FLIP_VERTICAL)
        )


__all__ = ["InputTransformContextualToolbarPage"]

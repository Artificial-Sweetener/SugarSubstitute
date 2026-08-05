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

"""Present explicit whole-layer coverage preview actions over the Input canvas."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QHBoxLayout, QWidget
from qfluentwidgets import FluentIcon, TransparentToolButton  # type: ignore[import-untyped]

from sugarsubstitute_shared.presentation.localization import (
    app_text,
    set_localized_accessible_name,
    set_localized_tooltip,
)
from substitute.presentation.canvas.shared.canvas_chrome_metrics import (
    CANVAS_CHROME_CONTROL_HEIGHT,
    CANVAS_CHROME_GAP,
    CANVAS_CHROME_SURFACE_BORDER_WIDTH,
    CANVAS_CHROME_SURFACE_PADDING,
)
from substitute.presentation.canvas.shared.canvas_control_frame import (
    CanvasControlFrame,
)
from substitute.presentation.canvas.shared.floating_canvas_surface import (
    floating_canvas_surface_stylesheet,
)
from substitute.presentation.localization import LocalizedPrimaryPushButton
from substitute.presentation.shell.chrome_style import connect_theme_refresh

from .input_coverage_modification_controls import (
    InputCoverageModificationControls,
)


class InputLayerCoverageEditor(CanvasControlFrame):
    """Own the bottom-centered operation editor for one exclusive preview mode."""

    previewRequested = Signal(object, int)
    applyRequested = Signal()
    cancelRequested = Signal()

    def __init__(self, parent: QWidget) -> None:
        """Build the canonical coverage controls with explicit Apply and Cancel."""
        super().__init__(parent)
        self.setObjectName("InputLayerCoverageEditor")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.controls = InputCoverageModificationControls(self)
        self.apply_button = LocalizedPrimaryPushButton(app_text("Apply"), self)
        self.apply_button.setObjectName("InputLayerCoverageApplyButton")
        self.close_button = TransparentToolButton(FluentIcon.CLOSE, self)
        self.close_button.setObjectName("InputLayerCoverageCancelButton")
        self.close_button.setFixedSize(
            CANVAS_CHROME_CONTROL_HEIGHT,
            CANVAS_CHROME_CONTROL_HEIGHT,
        )
        set_localized_tooltip(self.close_button, "Cancel")
        set_localized_accessible_name(self.close_button, "Cancel")

        content_inset = (
            CANVAS_CHROME_SURFACE_PADDING - CANVAS_CHROME_SURFACE_BORDER_WIDTH
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            content_inset,
            content_inset,
            content_inset,
            content_inset,
        )
        layout.setSpacing(CANVAS_CHROME_GAP)
        layout.addWidget(self.controls)
        layout.addWidget(self.apply_button)
        layout.addWidget(self.close_button)

        self.controls.valuesChanged.connect(self._request_preview)
        self.apply_button.clicked.connect(self.applyRequested.emit)
        self.close_button.clicked.connect(self.cancelRequested.emit)
        self._apply_theme_style()
        connect_theme_refresh(self, self._apply_theme_style)
        self.hide()

    def prepare(self) -> None:
        """Reset values and interaction for one newly captured mask revision."""
        self.controls.reset()
        self.set_applying(False)
        self.adjustSize()

    def request_current_preview(self) -> None:
        """Publish the current initial values after the mode is fully active."""
        self._request_preview()

    def set_applying(self, applying: bool) -> None:
        """Prevent additional changes after explicit settlement is requested."""
        enabled = not applying
        self.controls.setEnabled(enabled)
        self.apply_button.setEnabled(enabled)
        self.close_button.setEnabled(enabled)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Cancel the exclusive edit when Escape is pressed before Apply."""
        if event.key() == Qt.Key.Key_Escape and self.close_button.isEnabled():
            self.cancelRequested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def _request_preview(self) -> None:
        """Publish one operation and amount pair from the shared editor."""
        self.previewRequested.emit(
            self.controls.operation(),
            self.controls.amount(),
        )

    def _apply_theme_style(self, *_args: object) -> None:
        """Apply the canonical floating canvas material."""
        self.setStyleSheet(
            floating_canvas_surface_stylesheet("QFrame#InputLayerCoverageEditor")
        )


__all__ = ["InputLayerCoverageEditor"]

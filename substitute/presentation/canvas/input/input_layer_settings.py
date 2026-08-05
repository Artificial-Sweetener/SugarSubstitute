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

"""Present settings for one active Input mask layer."""

from __future__ import annotations

from uuid import UUID

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QGridLayout, QWidget
from cutecanvas import MaskInfo
from qfluentwidgets import (  # type: ignore[import-untyped]
    CaptionLabel,
    Slider,
)

from sugarsubstitute_shared.presentation.localization import (
    app_text,
)
from substitute.presentation.canvas.shared.canvas_chrome_metrics import (
    CANVAS_CHROME_GAP,
)
from substitute.presentation.localization import (
    LocalizedCaptionLabel,
    LocalizedPushButton,
)

from .input_tool_options_contracts import InputToolOptionsDocumentPort


class InputMaskLayerSettings(QWidget):
    """Own visual opacity and entry into exclusive layer coverage editing."""

    closeRequested = Signal()
    coverageEditRequested = Signal(object)

    def __init__(
        self,
        document: InputToolOptionsDocumentPort,
        parent: QWidget,
    ) -> None:
        """Build layer presentation controls and the coverage-edit action."""
        super().__init__(parent)
        self.setObjectName("InputMaskLayerSettings")
        self._document = document
        self._mask_id: UUID | None = None
        self._synchronizing = False
        self.opacity_slider = Slider(Qt.Orientation.Horizontal, self)
        self.opacity_slider.setObjectName("InputLayerVisualOpacity")
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setFixedWidth(132)
        self.opacity_value = CaptionLabel("", self)
        self.opacity_value.setMinimumWidth(36)

        self.edit_coverage_button = LocalizedPushButton(
            app_text("Edit layer coverage"),
            self,
        )
        self.edit_coverage_button.setObjectName("InputEditLayerCoverageButton")

        layout = QGridLayout(self)
        layout.setContentsMargins(
            CANVAS_CHROME_GAP,
            CANVAS_CHROME_GAP,
            CANVAS_CHROME_GAP,
            CANVAS_CHROME_GAP,
        )
        layout.setHorizontalSpacing(CANVAS_CHROME_GAP)
        layout.setVerticalSpacing(CANVAS_CHROME_GAP // 2)
        layout.addWidget(
            LocalizedCaptionLabel(app_text("Visual opacity"), self),
            0,
            0,
        )
        layout.addWidget(self.opacity_slider, 0, 1)
        layout.addWidget(self.opacity_value, 0, 2)
        layout.addWidget(self.edit_coverage_button, 1, 0, 1, 3)

        self.opacity_slider.valueChanged.connect(self._apply_opacity)
        self.edit_coverage_button.clicked.connect(self._request_coverage_edit)

    def set_layer(self, layer: MaskInfo | None) -> None:
        """Project one layer's current presentation without rewriting coverage."""
        next_mask_id = None if layer is None else layer.mask_id
        self._mask_id = next_mask_id
        opacity = 1.0 if layer is None or layer.opacity is None else layer.opacity
        self._synchronizing = True
        try:
            value = round(opacity * 100.0)
            self.opacity_slider.setValue(value)
            self.opacity_value.setText(f"{value}%")
        finally:
            self._synchronizing = False
        self.setEnabled(layer is not None)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Close layer properties when Escape is pressed."""
        if event.key() == Qt.Key.Key_Escape:
            self.closeRequested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def _apply_opacity(self, value: int) -> None:
        """Apply final presentation opacity without changing authored mask values."""
        self.opacity_value.setText(f"{value}%")
        if not self._synchronizing and self._mask_id is not None:
            self._document.set_mask_visual_opacity(self._mask_id, value / 100.0)

    def _request_coverage_edit(self) -> None:
        """Request exclusive editing for the currently presented mask layer."""
        if self._mask_id is not None:
            self.coverageEditRequested.emit(self._mask_id)


__all__ = ["InputMaskLayerSettings"]

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
from PySide6.QtWidgets import QVBoxLayout, QWidget
from cutecanvas import MaskInfo

from sugarsubstitute_shared.presentation.localization import (
    app_text,
)
from substitute.presentation.canvas.shared.canvas_chrome_metrics import (
    CANVAS_CHROME_GAP,
)
from substitute.presentation.localization import LocalizedPushButton


class InputMaskLayerSettings(QWidget):
    """Own entry into exclusive layer coverage editing."""

    closeRequested = Signal()
    coverageEditRequested = Signal(object)

    def __init__(
        self,
        parent: QWidget,
    ) -> None:
        """Build the active layer's coverage-edit action."""
        super().__init__(parent)
        self.setObjectName("InputMaskLayerSettings")
        self._mask_id: UUID | None = None

        self.edit_coverage_button = LocalizedPushButton(
            app_text("Edit layer coverage"),
            self,
        )
        self.edit_coverage_button.setObjectName("InputEditLayerCoverageButton")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            CANVAS_CHROME_GAP,
            CANVAS_CHROME_GAP,
            CANVAS_CHROME_GAP,
            CANVAS_CHROME_GAP,
        )
        layout.setSpacing(0)
        layout.addWidget(self.edit_coverage_button)

        self.edit_coverage_button.clicked.connect(self._request_coverage_edit)

    def set_layer(self, layer: MaskInfo | None) -> None:
        """Project one layer's current presentation without rewriting coverage."""
        next_mask_id = None if layer is None else layer.mask_id
        self._mask_id = next_mask_id
        self.setEnabled(layer is not None)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Close layer properties when Escape is pressed."""
        if event.key() == Qt.Key.Key_Escape:
            self.closeRequested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def _request_coverage_edit(self) -> None:
        """Request exclusive editing for the currently presented mask layer."""
        if self._mask_id is not None:
            self.coverageEditRequested.emit(self._mask_id)


__all__ = ["InputMaskLayerSettings"]

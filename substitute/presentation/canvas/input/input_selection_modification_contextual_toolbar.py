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

"""Present one explicit pixel-selection modification transaction."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QWidget
from substitute.presentation.canvas.shared.canvas_chrome_metrics import (
    CANVAS_CHROME_GAP,
)
from substitute.presentation.canvas.shared.contextual_toolbar import (
    ContextualToolbarPage,
    ContextualToolbarSettlementControls,
)

from .input_coverage_modification_controls import (
    InputCoverageModificationControls,
)


class InputSelectionModificationContextualToolbarPage(ContextualToolbarPage):
    """Own the single-line controls for one reversible selection preview."""

    previewRequested = Signal(object, int)
    applyRequested = Signal()
    cancelRequested = Signal()

    def __init__(self, parent: QWidget) -> None:
        """Build operation, amount, Cancel, and Apply on one toolbar row."""

        super().__init__(parent)
        self.controls = InputCoverageModificationControls(self, content_margin=0)
        self.controls.setObjectName("ContextualToolbarSelectionModificationControls")
        self.settlement_controls = ContextualToolbarSettlementControls(self)
        self.cancel_button = self.settlement_controls.cancel_button
        self.apply_button = self.settlement_controls.apply_button
        self.cancel_button.setObjectName(
            "ContextualToolbarSelectionModificationCancelButton"
        )
        self.apply_button.setObjectName(
            "ContextualToolbarSelectionModificationApplyButton"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(CANVAS_CHROME_GAP // 2)
        layout.addWidget(self.controls)
        layout.addWidget(self.settlement_controls)

        self.controls.valuesChanged.connect(self._request_preview)
        self.settlement_controls.cancelRequested.connect(self.cancelRequested.emit)
        self.settlement_controls.applyRequested.connect(self.applyRequested.emit)

    def request_initial_preview(self) -> None:
        """Publish the initial visible value after controller wiring is complete."""

        self._request_preview()

    def set_settlement_enabled(self, enabled: bool) -> None:
        """Prevent duplicate settlement while preserving the visible preview."""

        self.controls.setEnabled(enabled)
        self.settlement_controls.setEnabled(enabled)

    def _request_preview(self, *_args: object) -> None:
        """Publish the current operation and value as one replace request."""

        self.previewRequested.emit(self.controls.operation(), self.controls.amount())


__all__ = ["InputSelectionModificationContextualToolbarPage"]

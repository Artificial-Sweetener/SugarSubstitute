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

"""Present generic resolution controls for one unresolved Input edit session."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QWidget

from sugarsubstitute_shared.localization import ApplicationText
from substitute.presentation.canvas.shared.canvas_chrome_metrics import (
    CANVAS_CHROME_GAP,
)
from substitute.presentation.canvas.shared.contextual_toolbar import (
    ContextualToolbarHistoryControls,
    ContextualToolbarPage,
    ContextualToolbarSettlementControls,
)
from substitute.presentation.localization import LocalizedStrongBodyLabel


class InputEditSessionContextualToolbarPage(ContextualToolbarPage):
    """Expose unified history and settlement for any declared session tool."""

    undoRequested = Signal()
    redoRequested = Signal()
    applyRequested = Signal()
    cancelRequested = Signal()

    def __init__(self, label: ApplicationText | None, parent: QWidget) -> None:
        """Build one generic session page from host-localized tool identity."""

        super().__init__(parent)
        self.label = None if label is None else LocalizedStrongBodyLabel(label, self)
        self.history_controls = ContextualToolbarHistoryControls(self)
        self.settlement_controls = ContextualToolbarSettlementControls(self)
        self.apply_button = self.settlement_controls.apply_button
        self.cancel_button = self.settlement_controls.cancel_button
        self.apply_button.setObjectName("ContextualToolbarEditSessionApplyButton")
        self.cancel_button.setObjectName("ContextualToolbarEditSessionCancelButton")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(CANVAS_CHROME_GAP // 2)
        if self.label is not None:
            layout.addWidget(self.label)
        layout.addWidget(self.history_controls)
        layout.addWidget(self.settlement_controls)

        self.history_controls.undoRequested.connect(self.undoRequested.emit)
        self.history_controls.redoRequested.connect(self.redoRequested.emit)
        self.settlement_controls.applyRequested.connect(self.applyRequested.emit)
        self.settlement_controls.cancelRequested.connect(self.cancelRequested.emit)

    def set_available(
        self,
        *,
        undo: bool,
        redo: bool,
        apply: bool,
        cancel: bool,
    ) -> None:
        """Project one complete public session command state."""

        self.history_controls.set_available(undo=undo, redo=redo)
        self.apply_button.setEnabled(apply)
        self.cancel_button.setEnabled(cancel)


__all__ = ["InputEditSessionContextualToolbarPage"]

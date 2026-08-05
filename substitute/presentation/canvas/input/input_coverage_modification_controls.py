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

"""Present shared expand, contract, and feather value controls."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QWidget
from cutecanvas import LayerEdgeOperation
from qfluentwidgets import ComboBox  # type: ignore[import-untyped]

from sugarsubstitute_shared.presentation.localization import (
    LocalizedComboItem,
    app_text,
    set_localized_combo_items,
)
from substitute.presentation.canvas.shared.canvas_chrome_metrics import (
    CANVAS_CHROME_CONTROL_HEIGHT,
    CANVAS_CHROME_GAP,
)
from substitute.presentation.localization import LocalizedCaptionLabel
from substitute.presentation.widgets import SpinBox

_DEFAULT_PIXEL_AMOUNT = 4
_MAXIMUM_PIXEL_AMOUNT = 999
_PIXEL_AMOUNT_WIDTH = 42


class InputCoverageModificationControls(QWidget):
    """Own the canonical Input coverage operation and pixel amount editor."""

    valuesChanged = Signal()

    def __init__(
        self, parent: QWidget, *, content_margin: int = CANVAS_CHROME_GAP
    ) -> None:
        """Build the shared compact row with owner-selected outer spacing."""
        super().__init__(parent)
        self._synchronizing = False
        self.operation_selector = ComboBox(self)
        self.operation_selector.setObjectName("InputCoverageOperationSelector")
        set_localized_combo_items(
            self.operation_selector,
            (
                LocalizedComboItem(LayerEdgeOperation.EXPAND, app_text("Expand")),
                LocalizedComboItem(LayerEdgeOperation.CONTRACT, app_text("Contract")),
                LocalizedComboItem(LayerEdgeOperation.FEATHER, app_text("Feather")),
            ),
        )
        self.pixel_amount = SpinBox(self)
        self.pixel_amount.setObjectName("InputCoveragePixelAmount")
        self.pixel_amount.setRange(1, _MAXIMUM_PIXEL_AMOUNT)
        self.pixel_amount.setValue(_DEFAULT_PIXEL_AMOUNT)
        self.pixel_amount.setFixedWidth(_PIXEL_AMOUNT_WIDTH)
        self.pixel_amount.setSymbolVisible(False)
        self.pixel_amount.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.operation_selector.setFixedHeight(CANVAS_CHROME_CONTROL_HEIGHT)
        self.pixel_amount.setFixedHeight(CANVAS_CHROME_CONTROL_HEIGHT)

        layout = QGridLayout(self)
        layout.setContentsMargins(
            content_margin,
            content_margin,
            content_margin,
            content_margin,
        )
        layout.setHorizontalSpacing(CANVAS_CHROME_GAP)
        layout.setVerticalSpacing(0)
        layout.addWidget(self.operation_selector, 0, 0)
        layout.addWidget(
            LocalizedCaptionLabel(app_text("by"), self),
            0,
            1,
            alignment=Qt.AlignmentFlag.AlignLeft,
        )
        layout.addWidget(self.pixel_amount, 0, 2)
        layout.addWidget(
            LocalizedCaptionLabel(app_text("Pixels"), self),
            0,
            3,
            alignment=Qt.AlignmentFlag.AlignLeft,
        )

        self.operation_selector.currentIndexChanged.connect(self._values_changed)
        self.pixel_amount.valueChanged.connect(self._values_changed)

    def operation(self) -> LayerEdgeOperation:
        """Return the selected coverage operation."""
        value = self.operation_selector.currentData()
        if isinstance(value, LayerEdgeOperation):
            return value
        try:
            return LayerEdgeOperation(str(value.value))
        except (AttributeError, ValueError):
            return LayerEdgeOperation.EXPAND

    def amount(self) -> int:
        """Return the selected whole-pixel amount."""
        return self.pixel_amount.value()

    def reset(self) -> None:
        """Restore the canonical initial operation without publishing a preview."""
        self._synchronizing = True
        try:
            self.operation_selector.setCurrentIndex(0)
            self.pixel_amount.setValue(_DEFAULT_PIXEL_AMOUNT)
        finally:
            self._synchronizing = False

    def _values_changed(self, *_args: object) -> None:
        """Publish one semantic change outside programmatic synchronization."""
        if not self._synchronizing:
            self.valuesChanged.emit()


__all__ = ["InputCoverageModificationControls"]

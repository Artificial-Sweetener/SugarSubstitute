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

"""Provide typed spin-box widgets used by editor factories."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QDoubleSpinBox,
    QSpinBox,
    QWidget,
)
from qfluentwidgets import FluentStyleSheet  # type: ignore[import-untyped]
from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
    setCustomStyleSheet,
)

from substitute.presentation.widgets.wheel_permission import wheel_event_is_allowed

_NATIVE_SPIN_BOX_TEXT_RECT_QSS = """
SpinBox,
DoubleSpinBox {
    padding: 2px 2px;
}

SpinBox[symbolVisible=false],
DoubleSpinBox[symbolVisible=false] {
    padding: 2px 2px;
}
"""
_QFLUENT_SPIN_BOX_SIZE_HINT_DELTA = QSize(6, 2)


def _native_spin_box_size_hint(size: QSize) -> QSize:
    """Return the pre-QFluent size hint for Substitute spin boxes."""

    return QSize(
        max(0, size.width() - _QFLUENT_SPIN_BOX_SIZE_HINT_DELTA.width()),
        max(0, size.height() - _QFLUENT_SPIN_BOX_SIZE_HINT_DELTA.height()),
    )


def _apply_wheel_step_without_text_selection(
    widget: QAbstractSpinBox,
    event: QWheelEvent,
) -> None:
    """Apply one wheel step without entering line-edit selection state."""

    wheel_delta = event.angleDelta().y()
    if wheel_delta == 0:
        event.ignore()
        return
    widget.stepBy(1 if wheel_delta > 0 else -1)
    widget.lineEdit().deselect()
    event.accept()


def _apply_qfluent_spin_box_style(widget: QAbstractSpinBox) -> None:
    """Register one custom spin box with QFluent's spin-box stylesheet."""

    widget.setProperty("transparent", True)
    widget.setProperty("symbolVisible", True)
    FluentStyleSheet.SPIN_BOX.apply(widget)
    setCustomStyleSheet(
        widget,
        _NATIVE_SPIN_BOX_TEXT_RECT_QSS,
        _NATIVE_SPIN_BOX_TEXT_RECT_QSS,
    )


class SpinBox(QSpinBox):
    """Integer spin box with explicit symbol-visibility control."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize spin box defaults."""

        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._symbol_visible = True
        _apply_qfluent_spin_box_style(self)

    def setSymbolVisible(self, is_visible: bool) -> None:
        """Toggle increment/decrement button visibility."""

        self._symbol_visible = is_visible
        self.setProperty("symbolVisible", is_visible)
        symbols = (
            QAbstractSpinBox.ButtonSymbols.UpDownArrows
            if is_visible
            else QAbstractSpinBox.ButtonSymbols.NoButtons
        )
        self.setButtonSymbols(symbols)
        self.setStyle(QApplication.style())

    def isSymbolVisible(self) -> bool:
        """Return whether spin symbols are currently visible."""

        return self._symbol_visible

    def sizeHint(self) -> QSize:
        """Return the size hint Substitute exposed before QFluent styling."""

        return _native_spin_box_size_hint(super().sizeHint())

    def minimumSizeHint(self) -> QSize:
        """Return the minimum size hint Substitute exposed before QFluent styling."""

        return _native_spin_box_size_hint(super().minimumSizeHint())

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Apply wheel stepping only when the active editor policy allows it."""

        if not wheel_event_is_allowed(self, event):
            event.ignore()
            return
        _apply_wheel_step_without_text_selection(self, event)


class DoubleSpinBox(QDoubleSpinBox):
    """Floating-point spin box with stable trimmed text formatting."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize spin box defaults."""

        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._symbol_visible = True
        _apply_qfluent_spin_box_style(self)

    def setSymbolVisible(self, is_visible: bool) -> None:
        """Toggle increment/decrement button visibility."""

        self._symbol_visible = is_visible
        self.setProperty("symbolVisible", is_visible)
        symbols = (
            QAbstractSpinBox.ButtonSymbols.UpDownArrows
            if is_visible
            else QAbstractSpinBox.ButtonSymbols.NoButtons
        )
        self.setButtonSymbols(symbols)
        self.setStyle(QApplication.style())

    def isSymbolVisible(self) -> bool:
        """Return whether spin symbols are currently visible."""

        return self._symbol_visible

    def sizeHint(self) -> QSize:
        """Return the size hint Substitute exposed before QFluent styling."""

        return _native_spin_box_size_hint(super().sizeHint())

    def minimumSizeHint(self) -> QSize:
        """Return the minimum size hint Substitute exposed before QFluent styling."""

        return _native_spin_box_size_hint(super().minimumSizeHint())

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Apply wheel stepping only when the active editor policy allows it."""

        if not wheel_event_is_allowed(self, event):
            event.ignore()
            return
        _apply_wheel_step_without_text_selection(self, event)

    def textFromValue(self, value: float) -> str:
        """Render value without insignificant trailing zeroes."""

        text = f"{value:.10f}".rstrip("0").rstrip(".")
        if text in {"", "-0"}:
            return "0"
        return text


__all__ = [
    "DoubleSpinBox",
    "SpinBox",
]

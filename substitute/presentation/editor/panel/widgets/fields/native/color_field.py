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

"""Provide a Fluent color editor for native Comfy COLOR values."""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHBoxLayout, QWidget
from qfluentwidgets import ColorPickerButton, LineEdit  # type: ignore[import-untyped]


class ColorField(QWidget):
    """Edit one Comfy hexadecimal color through Fluent text and picker controls."""

    valueChanged = Signal(object)

    def __init__(self, value: object, parent: QWidget | None = None) -> None:
        """Initialize the field from a valid color or Comfy's white default."""

        super().__init__(parent)
        self.line_edit = LineEdit(self)
        self.line_edit.setFixedWidth(92)
        self.picker = ColorPickerButton(
            QColor(self._normalized_color(value)),
            self.tr("color"),
            self,
        )
        self.picker.setFixedWidth(48)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.line_edit)
        layout.addWidget(self.picker)

        self.setValue(value)
        self.line_edit.editingFinished.connect(self._commit_text)
        self.picker.colorChanged.connect(self._commit_picker_color)

    def value(self) -> str:
        """Return the normalized Comfy hexadecimal value."""

        return self._normalized_color(self.line_edit.text())

    def setValue(self, value: object) -> None:  # noqa: N802
        """Apply one color without emitting an application state change."""

        normalized = self._normalized_color(value)
        line_blocker = QSignalBlocker(self.line_edit)
        picker_blocker = QSignalBlocker(self.picker)
        self.line_edit.setText(normalized)
        self.picker.setColor(QColor(normalized))
        del line_blocker, picker_blocker

    def _commit_text(self) -> None:
        """Normalize edited text and publish a valid color."""

        raw_value = self.line_edit.text().strip()
        color = QColor(raw_value)
        if not color.isValid():
            self.line_edit.setText(self.value())
            return
        normalized = color.name(QColor.NameFormat.HexRgb)
        self.setValue(normalized)
        self.valueChanged.emit(normalized)

    def _commit_picker_color(self, color: QColor) -> None:
        """Publish a color selected through QFluent's themed dialog."""

        normalized = color.name(QColor.NameFormat.HexRgb)
        self.setValue(normalized)
        self.valueChanged.emit(normalized)

    @staticmethod
    def _normalized_color(value: object) -> str:
        """Return a valid lower-case hexadecimal color with a safe default."""

        color = QColor(value if isinstance(value, str) else "#ffffff")
        if not color.isValid():
            color = QColor("#ffffff")
        return color.name(QColor.NameFormat.HexRgb)


__all__ = ["ColorField"]

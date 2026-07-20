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

"""Provide a compact Fluent editor for native Comfy BOUNDING_BOX values."""

from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import QGridLayout, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    CaptionLabel,
    MessageBoxBase,
    PushButton,
    SpinBox,
    SubtitleLabel,
)

_BOX_KEYS = ("x", "y", "width", "height")
_DEFAULT_BOX = {"x": 0, "y": 0, "width": 512, "height": 512}


class _BoundingBoxDialog(MessageBoxBase):  # type: ignore[misc]
    """Edit four bounding-box coordinates in a themed modal surface."""

    def __init__(self, value: Mapping[str, int], parent: QWidget) -> None:
        """Build Fluent integer controls for one detached box value."""

        super().__init__(parent)
        self.title_label = SubtitleLabel(self.tr("Bounding box"), self)
        self.controls: dict[str, SpinBox] = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        for index, key in enumerate(_BOX_KEYS):
            label = CaptionLabel(key.upper(), self)
            control = SpinBox(self)
            control.setRange(
                -(2**31) if key in {"x", "y"} else 0,
                (2**31) - 1,
            )
            control.setValue(value[key])
            self.controls[key] = control
            row, column = divmod(index, 2)
            grid.addWidget(label, row * 2, column)
            grid.addWidget(control, row * 2 + 1, column)
        self.viewLayout.addWidget(self.title_label)
        self.viewLayout.addLayout(grid)
        self.widget.setMinimumWidth(420)

    def value(self) -> dict[str, int]:
        """Return the edited box value."""

        return {key: self.controls[key].value() for key in _BOX_KEYS}


class BoundingBoxField(PushButton):  # type: ignore[misc]
    """Open a Fluent coordinate dialog while retaining compact card geometry."""

    valueChanged = Signal(object)

    def __init__(self, value: object, parent: QWidget | None = None) -> None:
        """Initialize a compact editor from a normalized box mapping."""

        super().__init__(parent)
        self._value = self._normalized_box(value)
        self.clicked.connect(self._open_editor)
        self._refresh_text()

    def value(self) -> dict[str, int]:
        """Return a detached bounding-box mapping."""

        return dict(self._value)

    def setValue(self, value: object) -> None:  # noqa: N802
        """Apply a box value without emitting an application state change."""

        blocker = QSignalBlocker(self)
        self._value = self._normalized_box(value)
        self._refresh_text()
        del blocker

    def _open_editor(self) -> None:
        """Commit coordinates only when the Fluent dialog is accepted."""

        dialog = _BoundingBoxDialog(self._value, self.window())
        if not dialog.exec():
            return
        self._value = dialog.value()
        self._refresh_text()
        self.valueChanged.emit(self.value())

    def _refresh_text(self) -> None:
        """Summarize the current coordinates on the compact button."""

        self.setText(self.tr("x {x} · y {y} · {width}×{height}").format(**self._value))

    @staticmethod
    def _normalized_box(value: object) -> dict[str, int]:
        """Return a complete integer box while rejecting booleans and bad values."""

        source = value if isinstance(value, Mapping) else {}
        normalized: dict[str, int] = {}
        for key in _BOX_KEYS:
            candidate = source.get(key, _DEFAULT_BOX[key])
            normalized[key] = (
                int(candidate)
                if isinstance(candidate, int | float)
                and not isinstance(candidate, bool)
                else _DEFAULT_BOX[key]
            )
        normalized["width"] = max(0, normalized["width"])
        normalized["height"] = max(0, normalized["height"])
        return normalized


__all__ = ["BoundingBoxField"]

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

"""Provide synchronized spinner-slider controls for numeric presentation."""

from __future__ import annotations

import math

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QWidget

from .slider import DragOnlySlider
from .spin_box import DoubleSpinBox, SpinBox

_QT_SLIDER_MAXIMUM = 2_147_483_647


def spinner_slider_step_count(
    minimum: float,
    maximum: float,
    step: float,
) -> int | None:
    """Return a Qt-safe slider step count for one numeric range."""

    if not all(math.isfinite(item) for item in (minimum, maximum, step)):
        return None
    if step <= 0 or maximum < minimum:
        return None
    step_count = (maximum - minimum) / step
    if step_count > _QT_SLIDER_MAXIMUM:
        return None
    return max(1, int(round(step_count)))


class IntegerSpinnerSlider(QWidget):
    """Synchronize an integer spin box with a discrete horizontal slider."""

    valueChanged = Signal(int)

    def __init__(
        self,
        *,
        minimum: int,
        maximum: int,
        step: int,
        value: int,
        slider_width: int = 120,
        spinbox_width: int = 80,
        suffix: str = "",
        parent: QWidget | None = None,
    ) -> None:
        """Create one bounded integer spinner-slider pair."""

        super().__init__(parent)
        resolved_step = max(1, int(step))
        step_count = spinner_slider_step_count(
            float(minimum),
            float(maximum),
            float(resolved_step),
        )
        if step_count is None:
            raise ValueError("Spinner-slider range cannot fit Qt slider bounds.")
        self._minimum = int(minimum)
        self._step = resolved_step
        self.slider = DragOnlySlider(Qt.Orientation.Horizontal, self)
        self.slider.setRange(0, step_count)
        self.slider.setFixedWidth(slider_width)
        self.spinbox = SpinBox(self)
        self.spinbox.setRange(minimum, maximum)
        self.spinbox.setSingleStep(resolved_step)
        self.spinbox.setSuffix(suffix)
        self.spinbox.setSymbolVisible(False)
        self.spinbox.setFixedWidth(spinbox_width)
        self._build_layout()
        self.spinbox.setValue(value)
        self.slider.setValue(self._value_to_slider(self.spinbox.value()))
        self.slider.valueChanged.connect(self._apply_slider_position)
        self.spinbox.valueChanged.connect(self._apply_spinbox_value)

    def value(self) -> int:
        """Return the current integer value."""

        return int(self.spinbox.value())

    def setValue(self, value: int) -> None:
        """Set the value through the authoritative spin box."""

        self.spinbox.setValue(value)

    def _build_layout(self) -> None:
        """Arrange the spin box and slider as one compact control."""

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.spinbox, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.slider, 0, Qt.AlignmentFlag.AlignVCenter)

    def _slider_to_value(self, position: int) -> int:
        """Return the integer represented by one slider position."""

        return self._minimum + position * self._step

    def _value_to_slider(self, value: int) -> int:
        """Return the nearest slider position for one integer value."""

        return int(round((value - self._minimum) / self._step))

    def _apply_slider_position(self, position: int) -> None:
        """Apply one slider position through the spin-box value owner."""

        self.spinbox.setValue(self._slider_to_value(position))

    def _apply_spinbox_value(self, value: int) -> None:
        """Synchronize the slider and publish one value change."""

        self.slider.blockSignals(True)
        self.slider.setValue(self._value_to_slider(value))
        self.slider.blockSignals(False)
        self.valueChanged.emit(value)


class DecimalSpinnerSlider(QWidget):
    """Synchronize a decimal spin box with a discrete horizontal slider."""

    valueChanged = Signal(float)

    def __init__(
        self,
        *,
        minimum: float,
        maximum: float,
        step: float,
        value: float,
        decimals: int = 2,
        slider_width: int = 120,
        spinbox_width: int = 80,
        suffix: str = "",
        parent: QWidget | None = None,
    ) -> None:
        """Create one bounded decimal spinner-slider pair."""

        super().__init__(parent)
        step_count = spinner_slider_step_count(minimum, maximum, step)
        if step_count is None:
            raise ValueError("Spinner-slider range cannot fit Qt slider bounds.")
        self._minimum = float(minimum)
        self._step = float(step)
        self.slider = DragOnlySlider(Qt.Orientation.Horizontal, self)
        self.slider.setRange(0, step_count)
        self.slider.setFixedWidth(slider_width)
        self.spinbox = DoubleSpinBox(self)
        self.spinbox.setRange(minimum, maximum)
        self.spinbox.setSingleStep(step)
        self.spinbox.setDecimals(decimals)
        self.spinbox.setSuffix(suffix)
        self.spinbox.setSymbolVisible(False)
        self.spinbox.setFixedWidth(spinbox_width)
        self._build_layout()
        self.spinbox.setValue(value)
        self.slider.setValue(self._value_to_slider(self.spinbox.value()))
        self.slider.valueChanged.connect(self._apply_slider_position)
        self.spinbox.valueChanged.connect(self._apply_spinbox_value)

    def value(self) -> float:
        """Return the current decimal value."""

        return float(self.spinbox.value())

    def setValue(self, value: float) -> None:
        """Set the value through the authoritative spin box."""

        self.spinbox.setValue(value)

    def _build_layout(self) -> None:
        """Arrange the spin box and slider as one compact control."""

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.spinbox, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.slider, 0, Qt.AlignmentFlag.AlignVCenter)

    def _slider_to_value(self, position: int) -> float:
        """Return the decimal represented by one slider position."""

        return round(self._minimum + position * self._step, 10)

    def _value_to_slider(self, value: float) -> int:
        """Return the nearest slider position for one decimal value."""

        return int(round((value - self._minimum) / self._step))

    def _apply_slider_position(self, position: int) -> None:
        """Apply one slider position through the spin-box value owner."""

        self.spinbox.setValue(self._slider_to_value(position))

    def _apply_spinbox_value(self, value: float) -> None:
        """Synchronize the slider and publish one value change."""

        self.slider.blockSignals(True)
        self.slider.setValue(self._value_to_slider(value))
        self.slider.blockSignals(False)
        self.valueChanged.emit(value)


__all__ = [
    "DecimalSpinnerSlider",
    "IntegerSpinnerSlider",
    "spinner_slider_step_count",
]

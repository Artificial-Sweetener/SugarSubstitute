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

"""Widget contracts for reusable synchronized spinner-slider controls."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from substitute.presentation.widgets import (
    DecimalSpinnerSlider,
    IntegerSpinnerSlider,
)


def test_integer_spinner_slider_synchronizes_both_controls() -> None:
    """Integer values should remain authoritative across either input surface."""

    _app()
    control = IntegerSpinnerSlider(
        minimum=1,
        maximum=100,
        step=1,
        value=75,
    )
    observed: list[int] = []
    control.valueChanged.connect(observed.append)

    control.slider.setValue(84)
    assert control.value() == 85

    control.spinbox.setValue(42)
    assert control.slider.value() == 41
    assert observed == [85, 42]
    control.close()


def test_decimal_spinner_slider_preserves_decimal_values_and_suffix() -> None:
    """Decimal entry should synchronize to the nearest slider step without truncation."""

    _app()
    control = DecimalSpinnerSlider(
        minimum=0.01,
        maximum=100.0,
        step=0.01,
        value=1.0,
        decimals=2,
        suffix=" MB",
    )

    control.spinbox.setValue(1.25)

    assert control.value() == 1.25
    assert control.slider.value() == 124
    assert control.spinbox.suffix() == " MB"
    control.slider.setValue(249)
    assert control.value() == 2.5
    control.close()


def _app() -> QApplication:
    """Return the existing QApplication or create one for widget tests."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])

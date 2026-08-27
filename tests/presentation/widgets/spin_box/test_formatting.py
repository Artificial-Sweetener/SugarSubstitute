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

"""Verify floating-point spin-box text formatting."""

from __future__ import annotations

from substitute.presentation.widgets.spin_box import DoubleSpinBox
from tests.support.qt.lifecycle import destroy_qt_object, ensure_qt_application


def test_text_from_value_trims_insignificant_zeroes() -> None:
    """Rendered values should omit insignificant fractional zeroes and dots."""

    ensure_qt_application()
    spin_box = DoubleSpinBox()

    assert spin_box.textFromValue(1.2300000000) == "1.23"
    assert spin_box.textFromValue(1.0000000000) == "1"
    destroy_qt_object(spin_box)

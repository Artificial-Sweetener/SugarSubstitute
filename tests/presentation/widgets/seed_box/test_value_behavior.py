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

"""Verify seed value and mode behavior through the real control."""

from __future__ import annotations

from substitute.presentation.widgets.seed_box import SeedBox
from tests.support.qt.lifecycle import destroy_qt_object, ensure_qt_application


def test_text_input_filters_non_numeric_content_and_clamps_to_range() -> None:
    """Text entry should retain one sign and digits within configured bounds."""

    ensure_qt_application()
    widget = SeedBox(minimum=-200, maximum=200)

    widget.line_edit.setText(" -12x3 ")
    assert widget.line_edit.text() == "-123"
    assert widget.value() == -123

    widget.line_edit.setText("999")
    assert widget.line_edit.text() == "200"
    assert widget.value() == 200
    destroy_qt_object(widget)


def test_effective_value_transition_is_published_once() -> None:
    """Sanitization should publish one value change for one effective transition."""

    ensure_qt_application()
    widget = SeedBox(minimum=0, maximum=100, allow_negative=False)
    changes: list[int] = []
    widget.valueChanged.connect(changes.append)

    widget.line_edit.setText("999")
    widget.line_edit.setText("100")

    assert widget.line_edit.text() == "100"
    assert changes == [100]
    destroy_qt_object(widget)


def test_optional_maximum_preserves_values_above_64_bit_unsigned_range() -> None:
    """An unbounded seed should retain integers beyond common native ceilings."""

    ensure_qt_application()
    widget = SeedBox()
    huge_value = 18_446_744_073_709_551_615 + 123

    widget.setValue(huge_value)

    assert widget.value() == huge_value
    destroy_qt_object(widget)


def test_explicit_modes_update_state_and_publish_each_transition() -> None:
    """Mode changes should update authoritative state and publish exact transitions."""

    ensure_qt_application()
    widget = SeedBox()
    changes: list[str] = []
    widget.modeChanged.connect(changes.append)

    widget.setMode("fixed")
    widget.setMode("random")

    assert widget.mode() == "random"
    assert changes == ["fixed", "random"]
    destroy_qt_object(widget)

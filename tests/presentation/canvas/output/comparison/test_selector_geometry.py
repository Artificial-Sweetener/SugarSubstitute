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

"""Verify Output comparison selector widgets and geometry."""

from __future__ import annotations


from tests.presentation.canvas.output.comparison.controller_support import (
    ButtonGroup,
    PickerItemStub,
    build_controller,
    record_width,
)


def test_compare_buttons_return_side_specific_widget_objects() -> None:
    """Compare button helpers should resolve base and comparison controls by side."""

    buttons = ButtonGroup()
    controller = build_controller(buttons=buttons)

    assert controller.compare_scene_button("base") is buttons.base_scene
    assert controller.compare_scene_button("comparison") is buttons.comparison_scene
    assert controller.compare_set_button("base") is buttons.base_set
    assert controller.compare_set_button("comparison") is buttons.comparison_set
    assert controller.compare_source_button("base") is buttons.base_source
    assert controller.compare_source_button("comparison") is buttons.comparison_source


def test_compare_source_picker_row_width_uses_widest_label() -> None:
    """Compare source row width should honor the minimum and measured labels."""

    measured: list[str] = []
    controller = build_controller(
        source_width_for_text=lambda text: record_width(measured, text),
        source_selector_min_width=44,
    )

    width = controller.compare_source_picker_row_width(
        (
            PickerItemStub("A"),
            PickerItemStub("Long label"),
        )
    )

    assert width == 100
    assert measured == ["A", "Long label"]

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

"""Expose shared presentation widget primitives used across editor and shell views."""

from __future__ import annotations


def __getattr__(name: str) -> object:
    """Load shared widgets lazily so lightweight test stubs stay valid."""

    if name == "ComboBox":
        from .combo_box import ComboBox

        return ComboBox
    if name == "LinkSelectorComboBox":
        from .link_selector_combo_box import LinkSelectorComboBox

        return LinkSelectorComboBox
    if name == "SeedBox":
        from .seed_box import SeedBox

        return SeedBox
    if name == "SpinBox":
        from .spin_box import SpinBox

        return SpinBox
    if name == "DoubleSpinBox":
        from .spin_box import DoubleSpinBox

        return DoubleSpinBox
    if name == "DragOnlySlider":
        from .slider import DragOnlySlider

        return DragOnlySlider
    if name == "IntegerSpinnerSlider":
        from .spinner_slider import IntegerSpinnerSlider

        return IntegerSpinnerSlider
    if name == "DecimalSpinnerSlider":
        from .spinner_slider import DecimalSpinnerSlider

        return DecimalSpinnerSlider
    if name == "AnchoredRowPicker":
        from .anchored_row_picker import AnchoredRowPicker

        return AnchoredRowPicker
    if name == "AnchoredRowPickerItem":
        from .anchored_row_picker import AnchoredRowPickerItem

        return AnchoredRowPickerItem
    if name == "AnchoredRowPickerRow":
        from .anchored_row_picker import AnchoredRowPickerRow

        return AnchoredRowPickerRow
    if name == "AnchoredRowPickerTextMode":
        from .anchored_row_picker import AnchoredRowPickerTextMode

        return AnchoredRowPickerTextMode
    if name == "AnchoredRowPickerView":
        from .anchored_row_picker import AnchoredRowPickerView

        return AnchoredRowPickerView
    if name == "ToggleDropDownToolButton":
        from .menu_buttons import ToggleDropDownToolButton

        return ToggleDropDownToolButton
    if name == "TogglePrimarySplitPushButton":
        from .menu_buttons import TogglePrimarySplitPushButton

        return TogglePrimarySplitPushButton
    if name == "ToggleSplitToolButton":
        from .menu_buttons import ToggleSplitToolButton

        return ToggleSplitToolButton
    if name == "ToggleTransparentDropDownToolButton":
        from .menu_buttons import ToggleTransparentDropDownToolButton

        return ToggleTransparentDropDownToolButton
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AnchoredRowPicker",
    "AnchoredRowPickerItem",
    "AnchoredRowPickerRow",
    "AnchoredRowPickerTextMode",
    "AnchoredRowPickerView",
    "ComboBox",
    "DecimalSpinnerSlider",
    "DoubleSpinBox",
    "DragOnlySlider",
    "IntegerSpinnerSlider",
    "LinkSelectorComboBox",
    "SeedBox",
    "SpinBox",
    "ToggleDropDownToolButton",
    "TogglePrimarySplitPushButton",
    "ToggleSplitToolButton",
    "ToggleTransparentDropDownToolButton",
]

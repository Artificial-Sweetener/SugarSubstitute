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

"""Type stubs for lazily exported presentation widgets."""

from __future__ import annotations

from .anchored_row_picker import AnchoredRowPicker as AnchoredRowPicker
from .anchored_row_picker import AnchoredRowPickerItem as AnchoredRowPickerItem
from .anchored_row_picker import AnchoredRowPickerRow as AnchoredRowPickerRow
from .anchored_row_picker import AnchoredRowPickerTextMode as AnchoredRowPickerTextMode
from .anchored_row_picker import AnchoredRowPickerView as AnchoredRowPickerView
from .combo_box import ComboBox as ComboBox
from .link_selector_combo_box import LinkSelectorComboBox as LinkSelectorComboBox
from .menu_buttons import ToggleDropDownToolButton as ToggleDropDownToolButton
from .menu_buttons import TogglePrimarySplitPushButton as TogglePrimarySplitPushButton
from .menu_buttons import ToggleSplitToolButton as ToggleSplitToolButton
from .menu_buttons import (
    ToggleTransparentDropDownToolButton as ToggleTransparentDropDownToolButton,
)
from .seed_box import SeedBox as SeedBox
from .slider import DragOnlySlider as DragOnlySlider
from .spin_box import DoubleSpinBox as DoubleSpinBox
from .spin_box import SpinBox as SpinBox

__all__ = [
    "AnchoredRowPicker",
    "AnchoredRowPickerItem",
    "AnchoredRowPickerRow",
    "AnchoredRowPickerTextMode",
    "AnchoredRowPickerView",
    "ComboBox",
    "DoubleSpinBox",
    "DragOnlySlider",
    "LinkSelectorComboBox",
    "SeedBox",
    "SpinBox",
    "ToggleDropDownToolButton",
    "TogglePrimarySplitPushButton",
    "ToggleSplitToolButton",
    "ToggleTransparentDropDownToolButton",
]

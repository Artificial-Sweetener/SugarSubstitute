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

"""Verify real combo item and committed-selection behavior."""

from __future__ import annotations

from substitute.presentation.widgets.combo_box import ComboBox


def test_removing_item_left_of_current_preserves_selection(combo_box: ComboBox) -> None:
    """Removing an earlier item should shift the same committed item left."""

    combo_box.addItems(["A", "B", "C"])
    combo_box.setCurrentText("C")

    combo_box.removeItem(1)

    assert combo_box.currentIndex() == 1
    assert combo_box.currentText() == "C"
    assert [combo_box.itemText(index) for index in range(combo_box.count())] == [
        "A",
        "C",
    ]


def test_inserting_items_before_current_preserves_selection(
    combo_box: ComboBox,
) -> None:
    """Bulk insertion should shift the current index without changing its item."""

    combo_box.addItems(["A", "B"])
    combo_box.setCurrentText("B")

    combo_box.insertItems(0, ["X", "Y"])

    assert [combo_box.itemText(index) for index in range(combo_box.count())] == [
        "X",
        "Y",
        "A",
        "B",
    ]
    assert combo_box.currentIndex() == 3
    assert combo_box.currentText() == "B"


def test_maximum_hint_width_is_unset_by_default(combo_box: ComboBox) -> None:
    """A new combo should have no preferred-width cap."""

    assert combo_box.maxHintWidth() is None

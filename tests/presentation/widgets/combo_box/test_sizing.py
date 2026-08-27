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

"""Verify combo preferred, minimum, and closed-label sizing."""

from __future__ import annotations

import pytest

from substitute.presentation.widgets import combo_box as combo_box_module
from substitute.presentation.widgets.combo_box import ComboBox

_LONG_TEXT = "A much longer option that determines the preferred width"


def test_preferred_width_uses_widest_item(combo_box: ComboBox) -> None:
    """Selection changes should not alter the widest-item preferred width."""

    combo_box.addItems(["Short", _LONG_TEXT])
    short_width = combo_box.sizeHint().width()
    combo_box.setCurrentText(_LONG_TEXT)

    assert combo_box.sizeHint().width() == short_width
    assert short_width >= combo_box.fontMetrics().horizontalAdvance(_LONG_TEXT)


def test_preferred_width_grows_when_wider_item_is_added(combo_box: ComboBox) -> None:
    """Adding a wider item should update the preferred width without selecting it."""

    combo_box.addItem("Short")
    short_width = combo_box.sizeHint().width()
    combo_box.addItem(_LONG_TEXT)

    assert combo_box.currentText() == "Short"
    assert combo_box.sizeHint().width() > short_width


def test_preferred_width_resets_after_items_are_cleared(combo_box: ComboBox) -> None:
    """Clearing should discard the previous widest-item cache."""

    combo_box.addItem(_LONG_TEXT)
    long_width = combo_box.sizeHint().width()
    combo_box.clear()
    combo_box.addItem("Short")

    assert combo_box.sizeHint().width() < long_width


def test_maximum_hint_caps_preferred_width_only(combo_box: ComboBox) -> None:
    """A hint cap should preserve shrinkability and the widget's maximum width."""

    combo_box.addItem(_LONG_TEXT * 2)
    uncapped_width = combo_box.sizeHint().width()
    combo_box.setMaxHintWidth(320)

    assert combo_box.sizeHint().width() <= 320
    assert combo_box.sizeHint().width() >= combo_box.minimumSizeHint().width()
    assert combo_box.maximumWidth() > 320

    combo_box.setMaxHintWidth(None)
    assert combo_box.sizeHint().width() == uncapped_width


def test_selection_changes_keep_stable_preferred_width(combo_box: ComboBox) -> None:
    """Every existing selection should retain one stable layout demand."""

    combo_box.addItems(["Short", "Medium length", _LONG_TEXT])
    widths = []
    for text in ("Short", _LONG_TEXT, "Medium length"):
        combo_box.setCurrentText(text)
        widths.append(combo_box.sizeHint().width())

    assert len(set(widths)) == 1


def test_minimum_hint_allows_pressure_elision(combo_box: ComboBox) -> None:
    """The minimum should remain narrower than the widest-item preference."""

    combo_box.addItem(_LONG_TEXT)

    assert combo_box.minimumSizeHint().width() < combo_box.sizeHint().width()


def test_minimum_hint_does_not_reenter_size_hint(
    combo_box: ComboBox,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Minimum-width calculation should remain independent of sizeHint()."""

    combo_box.addItem(_LONG_TEXT)

    def fail_size_hint(self: object) -> None:
        """Reject recursive preferred-width calculation."""

        raise AssertionError("minimumSizeHint re-entered sizeHint")

    monkeypatch.setattr(ComboBox, "sizeHint", fail_size_hint)

    assert combo_box.minimumSizeHint().width() == (
        combo_box_module._COMBO_SHRINKABLE_MINIMUM_WIDTH
    )


def test_closed_text_elides_when_constrained(combo_box: ComboBox) -> None:
    """Closed display text should fit within the actual available text width."""

    combo_box.addItem(_LONG_TEXT)
    constrained_width = combo_box.minimumSizeHint().width()
    display_text = combo_box._closed_display_text_for_width(constrained_width)
    available_width = max(
        0,
        constrained_width - combo_box._closed_display_text_chrome_width(),
    )

    assert display_text != combo_box.currentText()
    assert combo_box.fontMetrics().horizontalAdvance(display_text) <= available_width


def test_closed_text_responds_to_allocated_width(combo_box: ComboBox) -> None:
    """Closed text should expand from elided to complete as width becomes available."""

    combo_box.addItem(_LONG_TEXT)
    narrow_text = combo_box._closed_display_text_for_width(
        combo_box.minimumSizeHint().width()
    )
    wide_text = combo_box._closed_display_text_for_width(combo_box.sizeHint().width())

    assert narrow_text != _LONG_TEXT
    assert wide_text == _LONG_TEXT
    assert len(wide_text) > len(narrow_text)

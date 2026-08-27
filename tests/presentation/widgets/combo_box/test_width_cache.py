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

"""Verify combo preferred-width cache invalidation boundaries."""

from __future__ import annotations

import pytest

from substitute.presentation.widgets.combo_box import ComboBox


def test_size_hint_uses_cached_widest_width(
    combo_box: ComboBox,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repeated size hints should not rescan item labels after mutation refresh."""

    combo_box.addItems(["Short", "A much longer option"])

    def fail_width_scan(self: object) -> None:
        """Reject an item scan from the size-hint read path."""

        raise AssertionError("sizeHint rescanned item text widths")

    monkeypatch.setattr(ComboBox, "_widest_item_text_width", fail_width_scan)

    assert combo_box.sizeHint().width() >= combo_box.minimumSizeHint().width()


def test_cached_width_refreshes_after_item_mutations(combo_box: ComboBox) -> None:
    """Every label mutation should refresh the cached preferred width exactly."""

    combo_box.addItems(["Short", "A much longer option"])
    long_width = combo_box.sizeHint().width()
    combo_box.setItemText(1, "Tiny")
    shortened_width = combo_box.sizeHint().width()
    combo_box.addItem("An even longer option than the original one")
    extended_width = combo_box.sizeHint().width()
    combo_box.removeItem(2)

    assert shortened_width < long_width
    assert extended_width > shortened_width
    assert combo_box.sizeHint().width() == shortened_width


def test_selection_change_does_not_invalidate_geometry(
    combo_box: ComboBox,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Selecting an existing item should repaint without changing layout demand."""

    combo_box.addItems(["Short", "A much longer option"])

    def fail_update_geometry() -> None:
        """Reject geometry invalidation for selection-only changes."""

        raise AssertionError("selection invalidated geometry")

    monkeypatch.setattr(combo_box, "updateGeometry", fail_update_geometry)

    combo_box.setCurrentText("A much longer option")
    assert combo_box.currentText() == "A much longer option"

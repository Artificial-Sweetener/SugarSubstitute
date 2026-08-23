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

"""Verify searchable popup opening, dismissal, and mounted refresh."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLabel

from tests.presentation.widgets.combo_box.support import MountedCombo
from tests.support.qt.semantic_wait import wait_for_qt_condition


def test_body_click_opens_full_dropdown(
    combo_mount: Callable[..., MountedCombo],
) -> None:
    """A body click should open every allowed item."""

    mounted = combo_mount()

    QTest.mouseClick(mounted.combo, Qt.MouseButton.LeftButton)

    popup = mounted.combo._popup
    assert popup is not None
    wait_for_qt_condition(popup.isVisible)
    assert popup.visible_texts() == [
        "Flat",
        "Euler",
        "Euclid",
        "Heun",
        "DPM++ 2M Karras",
        "Beta Euler",
    ]


def test_outside_click_closes_dropdown(
    combo_mount: Callable[..., MountedCombo],
) -> None:
    """A mouse press outside the combo and popup should dismiss it."""

    mounted = combo_mount()
    outside = _outside_label(mounted)
    QTest.mouseClick(mounted.combo, Qt.MouseButton.LeftButton)
    popup = mounted.combo._popup
    assert popup is not None
    wait_for_qt_condition(popup.isVisible)

    QTest.mouseClick(outside, Qt.MouseButton.LeftButton)

    wait_for_qt_condition(lambda: not popup.isVisible())


def test_outside_search_dismissal_restores_committed_text(
    combo_mount: Callable[..., MountedCombo],
) -> None:
    """Outside dismissal should abandon transient search without committing it."""

    mounted = combo_mount()
    outside = _outside_label(mounted)
    changed: list[str] = []
    mounted.combo.currentTextChanged.connect(changed.append)
    mounted.combo.setFocus()
    QTest.keyClicks(mounted.combo, "eu")
    popup = mounted.combo._popup
    assert popup is not None
    wait_for_qt_condition(popup.isVisible)

    QTest.mouseClick(outside, Qt.MouseButton.LeftButton)

    wait_for_qt_condition(lambda: not popup.isVisible())
    assert mounted.combo.text() == ""
    assert mounted.combo.currentText() == "Flat"
    assert changed == []


def test_visible_search_refresh_stays_left_anchored(
    combo_mount: Callable[..., MountedCombo],
) -> None:
    """In-place filtering should retain the combo's global left edge."""

    mounted = combo_mount()
    mounted.host.move(40, 40)
    mounted.combo.setFocus()
    QTest.keyClicks(mounted.combo, "a")
    popup = mounted.combo._popup
    assert popup is not None
    wait_for_qt_condition(popup.isVisible)
    initial_left = popup.list_global_left()

    QTest.keyClicks(mounted.combo, "r")

    assert initial_left == mounted.combo.mapToGlobal(mounted.combo.rect().topLeft()).x()
    assert popup.list_global_left() == initial_left


def test_search_popup_avoids_keyboard_grabbing_flags(
    combo_mount: Callable[..., MountedCombo],
) -> None:
    """The popup should preserve normal typing focus on the combo."""

    mounted = combo_mount()
    mounted.combo.setFocus()
    QTest.keyClicks(mounted.combo, "a")
    popup = mounted.combo._popup
    assert popup is not None
    wait_for_qt_condition(popup.isVisible)

    assert (popup.windowFlags() & Qt.WindowType.WindowType_Mask) != (
        Qt.WindowType.Popup
    )
    QTest.keyClicks(mounted.combo, "r")
    assert mounted.combo.text() == "ar"


def _outside_label(mounted: MountedCombo) -> QLabel:
    """Create one visible outside-click target under the harness owner."""

    outside = QLabel("Outside", mounted.host)
    outside.setGeometry(300, 20, 120, 34)
    outside.show()
    return outside

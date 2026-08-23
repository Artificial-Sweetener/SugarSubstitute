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

"""Verify searchable combo query, completion, and commit behavior."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from substitute.presentation.widgets.searchable_combo_popup import (
    SearchableComboPopup,
)
from tests.presentation.widgets.combo_box.support import MountedCombo
from tests.support.qt.semantic_wait import wait_for_qt_condition


def test_typing_filters_without_committing_selection(
    combo_mount: Callable[..., MountedCombo],
) -> None:
    """Typed query text should narrow results without publishing a selection."""

    mounted = combo_mount()
    changed: list[str] = []
    mounted.combo.currentTextChanged.connect(changed.append)

    _type_query(mounted, "heu")

    popup = _visible_popup(mounted)
    assert popup.visible_texts() == ["Heun"]
    assert mounted.combo.text() == "heu"
    assert mounted.combo.currentText() == "Flat"
    assert changed == []


def test_down_and_enter_commit_highlighted_result(
    combo_mount: Callable[..., MountedCombo],
) -> None:
    """Enter should commit the keyboard-highlighted allowed item."""

    mounted = combo_mount()
    changed: list[str] = []
    mounted.combo.currentTextChanged.connect(changed.append)
    _type_query(mounted, "eu")

    QTest.keyClick(mounted.combo, Qt.Key.Key_Down)
    QTest.keyClick(mounted.combo, Qt.Key.Key_Return)

    assert mounted.combo.currentText() == "Euclid"
    assert mounted.combo.text() == ""
    assert changed == ["Euclid"]


def test_tab_commits_highlighted_result(
    combo_mount: Callable[..., MountedCombo],
) -> None:
    """Tab should accept the current filtered result before focus traversal."""

    mounted = combo_mount()
    _type_query(mounted, "kar")

    QTest.keyClick(mounted.combo, Qt.Key.Key_Tab)

    assert mounted.combo.currentText() == "DPM++ 2M Karras"
    assert mounted.combo.text() == ""


def test_inline_completion_tracks_keyboard_highlight(
    combo_mount: Callable[..., MountedCombo],
) -> None:
    """Ghost completion should follow Up and Down result navigation."""

    mounted = combo_mount()
    _type_query(mounted, "eu")

    assert mounted.combo._inline_completion_suffix == "ler"
    QTest.keyClick(mounted.combo, Qt.Key.Key_Down)
    assert mounted.combo._inline_completion_suffix == "clid"
    QTest.keyClick(mounted.combo, Qt.Key.Key_Up)
    assert mounted.combo._inline_completion_suffix == "ler"


def test_inline_completion_tracks_hovered_result(
    combo_mount: Callable[..., MountedCombo],
) -> None:
    """Ghost completion should follow the row currently under the pointer."""

    mounted = combo_mount()
    _type_query(mounted, "eu")
    popup = _visible_popup(mounted)
    item = popup.view.item(1)
    assert item is not None

    popup._on_item_entered(item)

    assert mounted.combo._inline_completion_suffix == "clid"


def test_blank_search_ghosts_keyboard_highlight(
    combo_mount: Callable[..., MountedCombo],
) -> None:
    """Clearing selected text should ghost each fully highlighted item."""

    mounted = combo_mount()
    mounted.combo.setFocus()
    mounted.combo.selectAll()
    QTest.keyClick(mounted.combo, Qt.Key.Key_Backspace)

    assert mounted.combo.text() == ""
    assert mounted.combo._inline_completion_suffix == "Flat"
    QTest.keyClick(mounted.combo, Qt.Key.Key_Down)
    assert mounted.combo._inline_completion_suffix == "Euler"
    QTest.keyClick(mounted.combo, Qt.Key.Key_Down)
    assert mounted.combo._inline_completion_suffix == "Euclid"


def test_blank_search_ghosts_hovered_result(
    combo_mount: Callable[..., MountedCombo],
) -> None:
    """A hovered row should provide the whole ghost label for blank search."""

    mounted = combo_mount()
    mounted.combo.setFocus()
    mounted.combo.selectAll()
    QTest.keyClick(mounted.combo, Qt.Key.Key_Backspace)
    popup = _visible_popup(mounted)
    item = popup.view.item(2)
    assert item is not None

    popup._on_item_entered(item)

    assert mounted.combo.text() == ""
    assert mounted.combo._inline_completion_suffix == "Euclid"


def test_escape_restores_previous_committed_value(
    combo_mount: Callable[..., MountedCombo],
) -> None:
    """Escape should abandon query state without publishing a value change."""

    mounted = combo_mount()
    changed: list[str] = []
    mounted.combo.currentTextChanged.connect(changed.append)
    _type_query(mounted, "unknown")

    QTest.keyClick(mounted.combo, Qt.Key.Key_Escape)

    assert mounted.combo.currentText() == "Flat"
    assert mounted.combo.text() == ""
    assert changed == []


def test_unknown_return_text_is_not_added_or_committed(
    combo_mount: Callable[..., MountedCombo],
) -> None:
    """Return on no result should restore selection without inventing an item."""

    mounted = combo_mount()
    _type_query(mounted, "missing")

    QTest.keyClick(mounted.combo, Qt.Key.Key_Return)

    assert mounted.combo.currentText() == "Flat"
    assert mounted.combo.count() == 6
    assert mounted.combo.findText("missing") == -1


def test_typing_continues_when_popup_receives_key_events(
    combo_mount: Callable[..., MountedCombo],
) -> None:
    """Popup key routing should continue building the combo-owned query."""

    mounted = combo_mount()
    _type_query(mounted, "a")
    popup = _visible_popup(mounted)

    QTest.keyClicks(popup, "r")

    assert mounted.combo.text() == "ar"
    assert mounted.combo.currentText() == "Flat"
    assert popup.visible_texts() == ["DPM++ 2M Karras"]


def test_visible_popup_refines_without_reexecution(
    combo_mount: Callable[..., MountedCombo],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Search refinement should update the mounted popup in place."""

    mounted = combo_mount()
    _type_query(mounted, "a")
    popup = _visible_popup(mounted)

    def fail_exec(*_args: object, **_kwargs: object) -> object:
        """Reject a second popup execution during query refinement."""

        raise AssertionError("search refresh re-executed the popup")

    monkeypatch.setattr(popup, "exec", fail_exec)

    QTest.keyClicks(popup, "r")

    assert mounted.combo.text() == "ar"
    assert popup.isVisible()
    assert popup.visible_texts() == ["DPM++ 2M Karras"]


def test_typing_replaces_selected_committed_text(
    combo_mount: Callable[..., MountedCombo],
) -> None:
    """Typing over selected committed text should begin a fresh query."""

    mounted = combo_mount()
    mounted.combo.selectAll()

    QTest.keyClicks(mounted.combo, "a")

    popup = _visible_popup(mounted)
    assert mounted.combo.text() == "a"
    assert mounted.combo.currentText() == "Flat"
    assert popup.visible_texts() == ["Flat", "DPM++ 2M Karras", "Beta Euler"]


def _type_query(mounted: MountedCombo, text: str) -> None:
    """Enter one query through the real focused combo surface."""

    mounted.combo.setFocus()
    QTest.keyClicks(mounted.combo, text)


def _visible_popup(mounted: MountedCombo) -> SearchableComboPopup:
    """Return the combo popup after its observable visible state is published."""

    popup = mounted.combo._popup
    assert popup is not None
    wait_for_qt_condition(popup.isVisible)
    return popup

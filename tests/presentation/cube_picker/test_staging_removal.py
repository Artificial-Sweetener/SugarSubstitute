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

"""Cube staging removal interaction contracts."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFrame

from substitute.presentation.cube_picker.cube_staging_stack import CubeDraftStack
from tests.presentation.cube_picker.support import (
    ensure_application as _app,
    entry as _entry,
)
from tests.support.qt.lifecycle import destroy_qt_object
from tests.support.qt.semantic_wait import wait_for_qt_condition


def test_draft_stack_card_close_button_requests_removal() -> None:
    """Clicking a draft-card X button should remove that card from the draft stack."""

    _app()
    stack = CubeDraftStack()
    first = _entry("copy-a")
    second = _entry("copy-b")
    stack.insert_entry(0, first, QIcon())
    stack.insert_entry(1, second, QIcon())
    stack.remove_requested.connect(stack.remove_staged_id)
    stack.show()
    try:
        wait_for_qt_condition(stack.isVisible)
        first_card = stack.findChildren(QFrame, "cubeStagingCard")[0]
        close_button = getattr(first_card, "closeButton")
        close_button.click()

        wait_for_qt_condition(lambda: stack.entries() == (second,))
    finally:
        destroy_qt_object(stack)


def test_draft_stack_card_close_button_receives_mouse_clicks() -> None:
    """Mouse clicks on the X button should remove through the real button."""

    _app()
    stack = CubeDraftStack()
    first = _entry("copy-a")
    second = _entry("copy-b")
    stack.insert_entry(0, first, QIcon())
    stack.insert_entry(1, second, QIcon())
    stack.remove_requested.connect(stack.remove_staged_id)
    stack.show()
    try:
        wait_for_qt_condition(stack.isVisible)
        first_card = stack.findChildren(QFrame, "cubeStagingCard")[0]
        close_button = getattr(first_card, "closeButton")
        QTest.mouseClick(
            close_button,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            close_button.rect().center(),
        )

        wait_for_qt_condition(lambda: stack.entries() == (second,))
    finally:
        destroy_qt_object(stack)

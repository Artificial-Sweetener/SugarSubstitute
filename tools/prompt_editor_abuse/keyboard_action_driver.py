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

"""Dispatch prompt-editor abuse keys through real Qt input routes."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

_QT_KEYS = {
    "backspace": Qt.Key.Key_Backspace,
    "delete": Qt.Key.Key_Delete,
    "enter": Qt.Key.Key_Return,
    "escape": Qt.Key.Key_Escape,
    "left": Qt.Key.Key_Left,
    "right": Qt.Key.Key_Right,
    "up": Qt.Key.Key_Up,
    "down": Qt.Key.Key_Down,
    "home": Qt.Key.Key_Home,
    "end": Qt.Key.Key_End,
    "tab": Qt.Key.Key_Tab,
    "alt": Qt.Key.Key_Alt,
}


class PromptAbuseKeyboardActionDriver:
    """Own named key, chord, clipboard, undo, and redo dispatch."""

    def paste_text(self, target: QWidget, text: str) -> None:
        """Paste clipboard text through the focused production input route."""

        QApplication.clipboard().setText(text)
        QTest.keyClick(target, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)

    def dispatch_key(self, target: QWidget, key_name: str) -> None:
        """Dispatch one named editing key through its production route."""

        if key_name == "undo":
            QTest.keyClick(target, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
            return
        if key_name == "redo":
            QTest.keyClick(target, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
            return
        control_keys = {
            "copy": Qt.Key.Key_C,
            "cut": Qt.Key.Key_X,
            "select_all": Qt.Key.Key_A,
        }
        control_key = control_keys.get(key_name)
        if control_key is not None:
            QTest.keyClick(target, control_key, Qt.KeyboardModifier.ControlModifier)
            return
        modifier_name, separator, modified_key_name = key_name.partition("_")
        modifier = {
            "shift": Qt.KeyboardModifier.ShiftModifier,
            "control": Qt.KeyboardModifier.ControlModifier,
        }.get(modifier_name)
        if separator and modifier is not None:
            QTest.keyClick(target, self._named_key(modified_key_name), modifier)
            return
        QTest.keyClick(target, self._named_key(key_name))

    def press_key(self, target: QWidget, key_name: str) -> None:
        """Press one named key without releasing it."""

        QTest.keyPress(target, self._named_key(key_name))

    def release_key(self, target: QWidget, key_name: str) -> None:
        """Release one named key after a prior press."""

        QTest.keyRelease(target, self._named_key(key_name))

    def press_chord(self, target: QWidget, chord: str) -> None:
        """Dispatch one supported modifier chord through Qt's real key route."""

        modifier_name, separator, key_name = chord.partition("+")
        if separator != "+" or modifier_name != "alt":
            raise ValueError(f"Unsupported prompt abuse key chord {chord!r}.")
        QTest.keyPress(
            target,
            self._named_key(key_name),
            Qt.KeyboardModifier.AltModifier,
        )

    @staticmethod
    def _named_key(key_name: str) -> Qt.Key:
        """Return one supported Qt key by stable campaign name."""

        key = _QT_KEYS.get(key_name)
        if key is None:
            raise ValueError(f"Unsupported prompt abuse key {key_name!r}.")
        return key


__all__ = ["PromptAbuseKeyboardActionDriver"]

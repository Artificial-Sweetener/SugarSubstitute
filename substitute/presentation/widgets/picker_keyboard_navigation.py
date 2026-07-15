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

"""Normalize keyboard commands used by media-backed picker surfaces."""

from __future__ import annotations

from enum import Enum

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent


class PickerKeyboardAction(Enum):
    """Describe one normalized keyboard action for picker navigation."""

    ACTIVATE = "activate"
    DISMISS = "dismiss"
    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    DOWN = "down"


def picker_keyboard_action_for_key(
    key: int,
    *,
    tab_activates: bool = False,
    escape_dismisses: bool = False,
) -> PickerKeyboardAction | None:
    """Return the picker action represented by one Qt key code."""

    if key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
        return PickerKeyboardAction.ACTIVATE
    if tab_activates and key == Qt.Key.Key_Tab:
        return PickerKeyboardAction.ACTIVATE
    if escape_dismisses and key == Qt.Key.Key_Escape:
        return PickerKeyboardAction.DISMISS
    if key == Qt.Key.Key_Left:
        return PickerKeyboardAction.LEFT
    if key == Qt.Key.Key_Right:
        return PickerKeyboardAction.RIGHT
    if key == Qt.Key.Key_Up:
        return PickerKeyboardAction.UP
    if key == Qt.Key.Key_Down:
        return PickerKeyboardAction.DOWN
    return None


def picker_keyboard_action_from_event(
    event: QKeyEvent,
    *,
    tab_activates: bool = False,
    escape_dismisses: bool = False,
) -> PickerKeyboardAction | None:
    """Return the picker action for a key event with supported modifiers."""

    if event.modifiers() not in (
        Qt.KeyboardModifier.NoModifier,
        Qt.KeyboardModifier.KeypadModifier,
    ):
        return None
    return picker_keyboard_action_for_key(
        event.key(),
        tab_activates=tab_activates,
        escape_dismisses=escape_dismisses,
    )


__all__ = [
    "PickerKeyboardAction",
    "picker_keyboard_action_for_key",
    "picker_keyboard_action_from_event",
]

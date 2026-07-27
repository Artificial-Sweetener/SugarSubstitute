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

"""Translate Qt key events into safe, portable keyboard-control bindings."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QKeySequence
from sugarsubstitute_shared.presentation.localization import ApplicationText, app_text


class KeyboardBindingValidationError(ValueError):
    """Explain why a captured keyboard event cannot become a control binding."""

    def __init__(self, message: ApplicationText) -> None:
        """Retain the localized message while satisfying the exception contract."""

        self.message = message
        super().__init__(str(message))


_NAVIGATION_KEYS = frozenset(
    {
        Qt.Key.Key_Insert,
        Qt.Key.Key_Delete,
        Qt.Key.Key_Home,
        Qt.Key.Key_End,
        Qt.Key.Key_PageUp,
        Qt.Key.Key_PageDown,
    }
)
_MODIFIER_KEYS = frozenset(
    {
        Qt.Key.Key_Shift,
        Qt.Key.Key_Control,
        Qt.Key.Key_Alt,
        Qt.Key.Key_Meta,
        Qt.Key.Key_AltGr,
    }
)
_RESERVED_BINDINGS = frozenset({"Alt+F4", "Ctrl+Alt+Delete"})


def keyboard_binding_from_event(event: QKeyEvent) -> str:
    """Return a validated portable binding from one non-modifier key press."""

    key = event.key()
    if key in _MODIFIER_KEYS:
        raise KeyboardBindingValidationError(
            app_text("Press a key together with the modifier.")
        )
    sequence = QKeySequence(event.keyCombination())
    binding = sequence.toString(QKeySequence.SequenceFormat.PortableText)
    if not binding:
        raise KeyboardBindingValidationError(
            app_text("That key cannot be used as a control.")
        )
    if binding in _RESERVED_BINDINGS:
        raise KeyboardBindingValidationError(
            app_text("That combination is reserved by Windows.")
        )
    modifiers = event.modifiers()
    has_control_modifier = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
    has_alt_modifier = bool(modifiers & Qt.KeyboardModifier.AltModifier)
    is_function_key = Qt.Key.Key_F1 <= key <= Qt.Key.Key_F35
    if not (
        has_control_modifier
        or has_alt_modifier
        or is_function_key
        or key in _NAVIGATION_KEYS
    ):
        raise KeyboardBindingValidationError(
            app_text("Use Ctrl or Alt, a function key, or a navigation-cluster key.")
        )
    return binding


def keyboard_modifier_preview(event: QKeyEvent) -> str:
    """Return the visible modifier prefix while a capture control is active."""

    modifiers = event.modifiers()
    key = event.key()
    labels: list[str] = []
    if modifiers & Qt.KeyboardModifier.ControlModifier or key == Qt.Key.Key_Control:
        labels.append("Ctrl")
    if modifiers & Qt.KeyboardModifier.AltModifier or key == Qt.Key.Key_Alt:
        labels.append("Alt")
    if modifiers & Qt.KeyboardModifier.ShiftModifier or key == Qt.Key.Key_Shift:
        labels.append("Shift")
    if modifiers & Qt.KeyboardModifier.MetaModifier or key == Qt.Key.Key_Meta:
        labels.append("Meta")
    return " + ".join(labels) + (" +" if labels else "")


def display_keyboard_binding(binding: str | None) -> ApplicationText:
    """Render a stored binding consistently with spaced chord separators."""

    if not binding:
        return app_text("Not set")
    sequence = QKeySequence.fromString(
        binding, QKeySequence.SequenceFormat.PortableText
    )
    rendered = sequence.toString(QKeySequence.SequenceFormat.PortableText)
    return _spaced_binding_display(rendered or binding)


def _spaced_binding_display(binding: str) -> str:
    """Separate displayed chord parts so saved and live previews match."""

    return " + ".join(part.strip() for part in binding.split("+"))


__all__ = [
    "KeyboardBindingValidationError",
    "display_keyboard_binding",
    "keyboard_binding_from_event",
    "keyboard_modifier_preview",
]

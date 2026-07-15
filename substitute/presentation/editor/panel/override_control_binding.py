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

"""Bind toolbar override controls through committed semantic values."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from substitute.presentation.widgets import ComboBox

OverrideValueCommitted = Callable[[object], None]


def bind_override_control(
    widget: object,
    on_value_committed: OverrideValueCommitted,
) -> None:
    """Connect one override widget to its committed application value."""

    signal_target = getattr(widget, "spinbox", widget)
    if isinstance(widget, ComboBox):
        _connect(
            widget.currentTextChanged,
            lambda text: on_value_committed(_choice_value(widget, text)),
        )
        return
    if _connect_reader_signal(signal_target, "valueChanged", on_value_committed):
        return
    if _connect_reader_signal(widget, "checkedChanged", on_value_committed):
        return
    if _connect_reader_signal(widget, "stateChanged", on_value_committed):
        return
    if _connect_reader_signal(widget, "currentTextChanged", on_value_committed):
        return
    if _connect_reader_signal(widget, "imageSelected", on_value_committed):
        return
    if _connect_reader_signal(widget, "maskSelected", on_value_committed):
        return
    if _connect_reader_signal(widget, "editingFinished", on_value_committed):
        return
    _connect_reader_signal(widget, "textChanged", on_value_committed)


def _connect_reader_signal(
    widget: object,
    signal_name: str,
    callback: OverrideValueCommitted,
) -> bool:
    """Connect one available signal and read the committed widget value."""

    signal = getattr(widget, signal_name, None)
    if signal is None or not hasattr(signal, "connect"):
        return False

    def on_changed(*args: object) -> None:
        """Forward the widget's semantic value after its signal fires."""

        callback(_widget_value(widget, args))

    try:
        signal.connect(on_changed)
    except TypeError:
        return False
    return True


def _widget_value(widget: object, signal_args: tuple[object, ...]) -> object:
    """Return the application value represented by one override widget."""

    value = getattr(widget, "value", None)
    if callable(value):
        return value()
    is_checked = getattr(widget, "isChecked", None)
    if callable(is_checked):
        return bool(is_checked())
    current_text = getattr(widget, "currentText", None)
    if callable(current_text):
        return current_text()
    text = getattr(widget, "text", None)
    if callable(text):
        return text()
    current_file_path = getattr(widget, "current_file_path", None)
    if callable(current_file_path):
        return current_file_path()
    return signal_args[-1] if signal_args else None


def _choice_value(widget: object, text: object) -> object:
    """Resolve a committed choice label to its stored backend value."""

    label = str(text)
    values_by_label = getattr(widget, "_editor_choice_values_by_label", None)
    if isinstance(values_by_label, Mapping):
        return values_by_label.get(label, label)
    return label


def _connect(signal: Any, callback: Callable[[object], None]) -> None:
    """Connect one required semantic signal."""

    signal.connect(callback)


__all__ = ["bind_override_control"]

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

"""Measure prompt-editor keyboard, selection, and paste operations."""

from __future__ import annotations

from time import perf_counter
from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.editor.prompt_editor import PromptEditor

from .event_loop import process_events
from .scenarios import ScenarioOperation


def operation_key(operation: ScenarioOperation) -> Qt.Key:
    """Return the Qt key used for one non-text edit operation."""

    if operation == "backspace":
        return Qt.Key.Key_Backspace
    if operation == "delete":
        return Qt.Key.Key_Delete
    if operation == "enter":
        return Qt.Key.Key_Return
    raise ValueError(f"Unsupported key operation: {operation}")


def time_key_click(
    app: QApplication,
    editor: PromptEditor,
    *,
    character: str | None = None,
    key: Qt.Key | None = None,
) -> float:
    """Return elapsed milliseconds for one key operation plus event processing."""

    if character is None and key is None:
        raise ValueError("A character or key is required for performance timing.")
    target = prompt_key_target(editor)
    started_at = perf_counter()
    if character is not None:
        QTest.keyClicks(target, character)
    else:
        QTest.keyClick(target, cast(Qt.Key, key))
    process_events(app)
    return (perf_counter() - started_at) * 1000.0


def time_cursor_move_operations(
    app: QApplication,
    editor: PromptEditor,
    count: int,
) -> list[float]:
    """Measure user-facing left/right cursor movement."""

    timings: list[float] = []
    for index in range(count):
        key = Qt.Key.Key_Left if index % 2 == 0 else Qt.Key.Key_Right
        timings.append(time_key_click(app, editor, key=key))
    return timings


def time_selection_change_operations(
    app: QApplication,
    editor: PromptEditor,
    count: int,
) -> list[float]:
    """Measure user-facing selection extension and contraction."""

    timings: list[float] = []
    target = prompt_key_target(editor)
    for index in range(count):
        key = Qt.Key.Key_Right if index % 2 == 0 else Qt.Key.Key_Left
        started_at = perf_counter()
        QTest.keyClick(target, key, Qt.KeyboardModifier.ShiftModifier)
        process_events(app)
        timings.append((perf_counter() - started_at) * 1000.0)
    return timings


def time_paste_operation(
    app: QApplication,
    editor: PromptEditor,
    *,
    clipboard_text: str,
) -> float:
    """Measure one public paste operation with deterministic clipboard text."""

    QApplication.clipboard().setText(clipboard_text)
    started_at = perf_counter()
    editor.paste()
    process_events(app)
    return (perf_counter() - started_at) * 1000.0


def set_cursor_position(editor: PromptEditor, position: int) -> None:
    """Move the editor caret to one source offset before measuring operations."""

    cursor = editor.textCursor()
    cursor.setPosition(position, QTextCursor.MoveMode.MoveAnchor)
    editor.setTextCursor(cursor)


def prompt_key_target(editor: PromptEditor) -> QWidget:
    """Return the production focus widget that receives prompt key events."""

    focus_proxy = editor.focusProxy()
    return focus_proxy if isinstance(focus_proxy, QWidget) else editor


__all__ = [
    "operation_key",
    "prompt_key_target",
    "set_cursor_position",
    "time_cursor_move_operations",
    "time_key_click",
    "time_paste_operation",
    "time_selection_change_operations",
]

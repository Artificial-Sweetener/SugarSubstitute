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

"""Measure prompt-editor viewport and shell presentation operations."""

from __future__ import annotations

from time import perf_counter
from typing import cast

from PySide6.QtCore import QPoint
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.shell.context_menu_controller import (
    PromptShellContextMenuController,
)

from .event_loop import process_events
from .reorder_measurements import surface_for


def time_scroll_operations(
    app: QApplication,
    editor: PromptEditor,
    count: int,
) -> list[float]:
    """Measure scrollbar updates on the projection surface."""

    surface = surface_for(editor)
    scroll_bar = surface.verticalScrollBar()
    scroll_bar.setRange(0, max(scroll_bar.maximum(), count * 24))
    timings: list[float] = []
    for index in range(count):
        started_at = perf_counter()
        scroll_bar.setValue(min(scroll_bar.maximum(), (index + 1) * 24))
        process_events(app)
        timings.append((perf_counter() - started_at) * 1000.0)
    return timings


def time_resize_operations(
    app: QApplication,
    editor: PromptEditor,
    count: int,
) -> list[float]:
    """Measure prompt editor resize operations with event processing."""

    timings: list[float] = []
    for index in range(count):
        width = 680 + (index % 4) * 32
        height = 170 + (index % 3) * 12
        started_at = perf_counter()
        editor.resize(width, height)
        process_events(app)
        timings.append((perf_counter() - started_at) * 1000.0)
    return timings


def time_hover_operations(
    app: QApplication,
    editor: PromptEditor,
    count: int,
) -> list[float]:
    """Measure passive viewport hover movement over prepared projection tokens."""

    surface = surface_for(editor)
    viewport = surface.viewport()
    timings: list[float] = []
    for index in range(count):
        point = QPoint(12 + (index % 4) * 18, 12 + (index % 3) * 18)
        started_at = perf_counter()
        QTest.mouseMove(viewport, point)
        process_events(app)
        timings.append((perf_counter() - started_at) * 1000.0)
    return timings


def time_focus_operations(
    app: QApplication,
    editor: PromptEditor,
    count: int,
) -> list[float]:
    """Measure focus transitions through shell-owned focus routing."""

    timings: list[float] = []
    for _ in range(count):
        started_at = perf_counter()
        editor.clearFocus()
        process_events(app)
        editor.setFocus()
        process_events(app)
        timings.append((perf_counter() - started_at) * 1000.0)
    return timings


def time_context_menu_open(app: QApplication, editor: PromptEditor) -> float:
    """Measure prompt context-menu opening with menu execution patched to no-op."""

    context_menu = cast(
        PromptShellContextMenuController,
        getattr(editor, "_shell_context_menu"),
    )
    position = editor.cursorRect().center()
    global_position = editor.mapToGlobal(position)
    event = QContextMenuEvent(
        QContextMenuEvent.Reason.Mouse,
        position,
        global_position,
    )
    started_at = perf_counter()
    context_menu.show_prompt_context_menu(event)
    process_events(app)
    return (perf_counter() - started_at) * 1000.0


__all__ = [
    "time_context_menu_open",
    "time_focus_operations",
    "time_hover_operations",
    "time_resize_operations",
    "time_scroll_operations",
]

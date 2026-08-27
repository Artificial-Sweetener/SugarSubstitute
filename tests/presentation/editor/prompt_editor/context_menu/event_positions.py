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

"""Build deterministic prompt-editor context-menu events for capability tests."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import QPoint
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.editor.prompt_editor import PromptEditor
from tests.presentation.editor.prompt_editor.context_menu.mounting import (
    ensure_qapp,
    process_events,
    wait_for_prompt_editor_projection,
)
from tests.support.qt.semantic_wait import wait_for_qt_condition


def send_context_menu_event(target: QWidget) -> QPoint:
    """Send a mouse-originated context-menu event to the supplied widget."""

    app = ensure_qapp()
    local_pos = target.rect().center()
    global_pos = target.mapToGlobal(local_pos)
    QApplication.sendEvent(
        target,
        QContextMenuEvent(
            QContextMenuEvent.Reason.Mouse,
            local_pos,
            global_pos,
        ),
    )
    process_events(app)
    return global_pos


def shell_viewport(editor: PromptEditor) -> QWidget:
    """Return the host QFluent viewport watched by the prompt-editor filter."""

    return cast(QWidget, getattr(editor, "_shell_viewport")())


def context_event_for_source_text(
    editor: PromptEditor,
    source_text: str,
) -> QContextMenuEvent:
    """Build a context-menu event centered on visible source text."""

    cast(Any, editor)._shell_context_menu.record_context_menu_press()
    source_start = editor.toPlainText().index(source_text)
    source_end = source_start + len(source_text)
    wait_for_prompt_editor_projection(editor)
    wait_for_qt_condition(
        lambda: bool(editor.source_range_fragments(start=source_start, end=source_end))
    )
    fragment = editor.source_range_fragments(start=source_start, end=source_end)[0]
    global_pos = editor.viewport().mapToGlobal(fragment.center().toPoint())
    return QContextMenuEvent(
        QContextMenuEvent.Reason.Mouse,
        editor.mapFromGlobal(global_pos),
        global_pos,
    )


def prepared_context_event_for_source_text(
    editor: PromptEditor,
    source_text: str,
) -> QContextMenuEvent:
    """Prepare the clicked scene position and return its context-menu event."""

    event = context_event_for_source_text(editor, source_text)
    source_position = cast(
        Any, editor
    )._shell_context_menu._source_position_for_global_pos(event.globalPos())
    assert source_position is not None
    cast(Any, editor)._scene_position_preparation.prepare_position_context(
        source_position,
        reason="test_context_menu_scene_position",
    )
    return event


def prepare_context_menu_scene_position(
    editor: PromptEditor,
    source_text: str,
) -> None:
    """Prepare scene-position context for separately built menu events."""

    _ = prepared_context_event_for_source_text(editor, source_text)

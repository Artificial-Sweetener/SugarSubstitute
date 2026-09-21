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

"""Own exact source-cursor and pointer actions for prompt abuse workloads."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from .models import PromptAbuseAction
from .owner_state import capture_prompt_cursor_positions


class PromptAbuseSourceActionDriver:
    """Drive and verify authoritative source cursor state."""

    def mouse_caret(self, editor: object, position: int) -> None:
        """Place the caret through a real viewport click at a source boundary."""

        prompt_editor = cast(Any, editor)
        viewport = cast(QWidget, prompt_editor.viewport())
        QTest.mouseClick(
            viewport,
            Qt.MouseButton.LeftButton,
            pos=self.viewport_point_for_source_position(prompt_editor, position),
            delay=0,
        )

    def mouse_drag_selection(self, editor: object, start: int, end: int) -> None:
        """Create a directional selection through a real viewport pointer drag."""

        prompt_editor = cast(Any, editor)
        viewport = cast(QWidget, prompt_editor.viewport())
        start_point = self.viewport_point_for_source_position(prompt_editor, start)
        end_point = self.viewport_point_for_source_position(prompt_editor, end)
        QTest.mousePress(
            viewport,
            Qt.MouseButton.LeftButton,
            pos=start_point,
            delay=0,
        )
        QTest.mouseMove(viewport, end_point, delay=0)
        QTest.mouseRelease(
            viewport,
            Qt.MouseButton.LeftButton,
            pos=end_point,
            delay=0,
        )

    def select_range(self, editor: object, action: PromptAbuseAction) -> None:
        """Select one source range through the editor's authoritative cursor."""

        assert action.position is not None
        assert action.selection_end is not None
        prompt_editor = cast(Any, editor)
        cursor = prompt_editor.textCursor()
        cursor.setPosition(action.position, QTextCursor.MoveMode.MoveAnchor)
        cursor.setPosition(action.selection_end, QTextCursor.MoveMode.KeepAnchor)
        prompt_editor.setTextCursor(cursor)

    def move_cursor(self, editor: object, action: PromptAbuseAction) -> None:
        """Move the authoritative source cursor to one exact position."""

        assert action.position is not None
        prompt_editor = cast(Any, editor)
        cursor = prompt_editor.textCursor()
        cursor.setPosition(action.position, QTextCursor.MoveMode.MoveAnchor)
        prompt_editor.setTextCursor(cursor)

    @staticmethod
    def source_matches(editor: object, expected_source: str | None) -> bool:
        """Return whether an action's exact source checkpoint is satisfied."""

        return (
            expected_source is None
            or cast(Any, editor).toPlainText() == expected_source
        )

    @staticmethod
    def caret_matches(editor: object, expected_position: int | None) -> bool:
        """Return whether an action's exact logical caret checkpoint is satisfied."""

        return (
            expected_position is None
            or capture_prompt_cursor_positions(editor)[0] == expected_position
        )

    @staticmethod
    def anchor_matches(editor: object, expected_position: int | None) -> bool:
        """Return whether the authoritative selection anchor matches a checkpoint."""

        return (
            expected_position is None
            or capture_prompt_cursor_positions(editor)[1] == expected_position
        )

    @staticmethod
    def viewport_point_for_source_position(editor: Any, position: int) -> QPoint:
        """Return a viewport point on one authoritative source caret boundary."""

        surface = editor._surface
        caret_state = surface.projection_document().caret_map.state_for_source_position(
            position
        )
        rect = surface._layout.frame.geometry.caret.cursor_rect(
            caret_state,
            scroll_offset=surface._scroll_offset(),
        )
        return QPoint(round(rect.center().x()), round(rect.center().y()))


__all__ = ["PromptAbuseSourceActionDriver"]

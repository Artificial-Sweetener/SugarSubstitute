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

"""Contract tests for prompt-editor search state projected into source-line chrome."""

from __future__ import annotations


from PySide6.QtGui import QTextCursor

from tests.support.prompt_editor.visual_parity_support import (
    create_prompt_editor,
    ensure_qapp,
)
from tests.support.qt.lifecycle import destroy_qt_object


def test_prompt_projection_cursor_clear_selection_matches_qt_cursor_contract() -> None:
    """Projection cursor should support `clearSelection()` for compatibility callers."""

    app = ensure_qapp()
    editor = create_prompt_editor()
    try:
        editor.setPlainText("alpha beta")
        cursor = editor.textCursor()
        cursor.setPosition(0)
        cursor.movePosition(
            QTextCursor.MoveOperation.Right,
            QTextCursor.MoveMode.KeepAnchor,
            5,
        )
        editor.setTextCursor(cursor)

        live_cursor = editor.textCursor()
        live_cursor.clearSelection()
        editor.setTextCursor(live_cursor)
        app.processEvents()

        final_cursor = editor.textCursor()
        assert final_cursor.selectionStart() == final_cursor.selectionEnd() == 5
    finally:
        editor.close()
        destroy_qt_object(editor)

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

import os
from typing import Any, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QTextCursor

from tests.prompt_visual_test_helpers import create_prompt_editor, ensure_qapp


def test_prompt_editor_search_methods_publish_feature_snapshot_and_projection() -> None:
    """PromptEditor should publish feature search state and project paint ranges."""

    app = ensure_qapp()
    editor = create_prompt_editor()
    try:
        editor.setPlainText("alpha beta alpha")
        editor.set_search_matches(
            ((0, 5), (11, 5)),
            active_index=1,
            query_identity=("text", "alpha"),
        )
        app.processEvents()

        snapshot = cast(Any, editor)._search_feature_controller.snapshot
        assert snapshot.highlights.match_ranges == ((0, 5), (11, 5))
        assert snapshot.highlights.active_index == 1
        assert snapshot.identity.query_identity == ("text", "alpha")
        assert snapshot.identity.source_revision is not None
        session = editor._surface._session
        assert session.search_match_ranges == ((0, 5), (11, 5))
        assert session.active_search_match_index == 1
    finally:
        editor.close()
        editor.deleteLater()
        app.processEvents()


def test_prompt_editor_clear_search_matches_resets_feature_and_projection_state() -> (
    None
):
    """Clearing prompt search should remove feature and projection highlight state."""

    app = ensure_qapp()
    editor = create_prompt_editor()
    try:
        editor.setPlainText("alpha beta alpha")
        editor.set_search_matches(((0, 5),), active_index=0)
        editor.clear_search_matches()
        app.processEvents()

        snapshot = cast(Any, editor)._search_feature_controller.snapshot
        assert snapshot.highlights.match_ranges == ()
        assert snapshot.highlights.active_index is None
        assert snapshot.identity.query_identity is None
        session = editor._surface._session
        assert session.search_match_ranges == ()
        assert session.active_search_match_index is None
    finally:
        editor.close()
        editor.deleteLater()
        app.processEvents()


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
        editor.deleteLater()
        app.processEvents()

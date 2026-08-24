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

"""Verify exact-weight edit activation and commit behavior."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretPlacement,
)
from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)
from tests.support.prompt_editor.projection_surface_support import (
    first_emphasis_token,
    flush_projection_update_scheduler,
    flush_semantic_refresh,
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
)


def test_projection_surface_reclassifies_edited_literal_group_as_existing_emphasis_token(
    widgets: list[QWidget],
) -> None:
    """Typing a weight into an escaped literal should enter normal exact edit."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text=r"\(test\)",
        width=240,
    )
    surface = surface_for(box)
    cursor = box.textCursor()
    cursor.setPosition(len(r"\(test"))
    box.setTextCursor(cursor)

    QTest.keyClicks(box, ":1")
    flush_semantic_refresh(box)
    flush_projection_update_scheduler(surface)
    process_events(app)

    token = first_emphasis_token(box)
    assert box.toPlainText() == "(test:1)"
    assert token.display_text == "test"
    assert token.value_text == "1"
    assert token.editing_value_text == "1"
    assert token.editing_caret_index == 1
    assert token.editing_select_all is False
    assert token.source_start < box.textCursor().position() < token.source_end

    focused_widget = QApplication.focusWidget()
    assert focused_widget is not None
    QTest.keyClicks(focused_widget, ".20")
    process_events(app)

    editing_token = first_emphasis_token(box)
    assert box.toPlainText() == "(test:1)"
    assert editing_token.editing_value_text == "1.20"
    assert editing_token.editing_caret_index == 4

    QTest.keyClick(box, Qt.Key.Key_Return)
    process_events(app)

    committed_token = first_emphasis_token(box)
    assert box.toPlainText() == "(test:1.20)"
    assert committed_token.value_text == "1.20"
    assert committed_token.editing_value_text is None
    assert box.textCursor().position() == committed_token.source_end
    assert getattr(surface, "_cursor_state").placement is (
        PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE
    )


def test_projection_surface_space_after_inline_weight_stays_at_content_boundary(
    widgets: list[QWidget],
) -> None:
    """Direct Space should remain inside a weighted emphasis content boundary."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text=r"\(test\)",
        width=240,
    )
    cursor = box.textCursor()
    cursor.setPosition(len(r"\(test"))
    box.setTextCursor(cursor)

    QTest.keyClicks(box, ":1.20")
    process_events(app)
    QTest.keyClick(box, Qt.Key.Key_Space)
    process_events(app)

    token = first_emphasis_token(box)
    assert box.toPlainText() == "(test :1.20)"
    assert token.value_text == "1.20"
    assert token.editing_value_text is None
    assert box.textCursor().position() == len("(test ")


def test_projection_surface_space_commits_active_auto_exact_weight_edit(
    widgets: list[QWidget],
) -> None:
    """Space should commit an active auto-created exact edit before inserting."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text=r"\(test\)",
        width=240,
    )
    surface = surface_for(box)
    cursor = box.textCursor()
    cursor.setPosition(len(r"\(test"))
    box.setTextCursor(cursor)

    QTest.keyClicks(box, ":1")
    flush_semantic_refresh(box)
    flush_projection_update_scheduler(surface)
    process_events(app)
    focused_widget = QApplication.focusWidget()
    assert focused_widget is not None
    QTest.keyClicks(focused_widget, ".20")
    process_events(app)

    editing_token = first_emphasis_token(box)
    assert editing_token.editing_value_text == "1.20"

    QTest.keyClick(focused_widget, Qt.Key.Key_Space)
    process_events(app)

    committed_token = first_emphasis_token(box)
    assert box.toPlainText() == "(test:1.20) "
    assert committed_token.value_text == "1.20"
    assert committed_token.editing_value_text is None
    assert box.textCursor().position() == len("(test:1.20) ")


def test_projection_surface_auto_exact_weight_edit_uses_existing_click_commit_flow(
    widgets: list[QWidget],
) -> None:
    """Auto-created exact weight edits should hide text caret and commit on outside click."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text=r"\(test\), dog",
        width=260,
    )
    surface = surface_for(box)
    cursor = box.textCursor()
    cursor.setPosition(len(r"\(test"))
    box.setTextCursor(cursor)

    QTest.keyClicks(box, ":1")
    flush_semantic_refresh(box)
    flush_projection_update_scheduler(surface)
    process_events(app)
    focused_widget = QApplication.focusWidget()
    assert focused_widget is not None
    QTest.keyClicks(focused_widget, ".20")
    process_events(app)

    editing_token = first_emphasis_token(box)
    should_paint_caret = getattr(surface, "_should_paint_caret")
    assert box.toPlainText() == "(test:1), dog"
    assert editing_token.editing_value_text == "1.20"
    assert not should_paint_caret()

    token_rect = surface.token_anchor_rect(editing_token)
    assert token_rect is not None
    click_point = QPoint(int(token_rect.right() + 18), int(token_rect.center().y()))
    QTest.mouseClick(box.viewport(), Qt.MouseButton.LeftButton, pos=click_point)
    process_events(app)

    committed_token = first_emphasis_token(box)
    assert box.toPlainText() == "(test:1.20), dog"
    assert committed_token.value_text == "1.20"
    assert committed_token.editing_value_text is None

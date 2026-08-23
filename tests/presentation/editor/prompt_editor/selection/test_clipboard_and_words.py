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

"""Verify clipboard source text and word-selection refinement."""

from __future__ import annotations

import pytest

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)
from tests.presentation.editor.prompt_editor.selection.support import (
    _first_emphasis_token,
    _first_lora_token,
    _point_for_source_position,
)

pytestmark = pytest.mark.usefixtures("qt_clipboard_owner")


def test_projection_selection_copy_of_selected_token_returns_raw_source_text(
    widgets: list[QWidget],
) -> None:
    """Selecting a collapsed token should still copy the underlying raw prompt source."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), suffix",
        width=220,
    )
    token = _first_emphasis_token(box)
    cursor = box.textCursor()
    cursor.setPosition(token.source_start, QTextCursor.MoveMode.MoveAnchor)
    cursor.setPosition(token.source_end, QTextCursor.MoveMode.KeepAnchor)
    box.setTextCursor(cursor)
    process_events(app)
    box.copy()

    clipboard = QApplication.clipboard()
    assert clipboard.text() == "(cat:1.05)"
    assert box.textCursor().selectionStart() == token.source_start
    assert box.textCursor().selectionEnd() == token.source_end


def test_projection_selection_copy_of_selected_lora_token_returns_raw_source_text(
    widgets: list[QWidget],
) -> None:
    """Copying a decorated LoRA token should keep source-based clipboard semantics."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="<lora:midna:1>, suffix",
        width=220,
        syntaxes=("emphasis", "wildcard", "lora"),
    )
    token = _first_lora_token(box)
    cursor = box.textCursor()
    cursor.setPosition(token.source_start, QTextCursor.MoveMode.MoveAnchor)
    cursor.setPosition(token.source_end, QTextCursor.MoveMode.KeepAnchor)
    box.setTextCursor(cursor)
    process_events(app)
    box.copy()

    clipboard = QApplication.clipboard()
    assert clipboard.text() == "<lora:midna:1.00>"
    assert box.textCursor().selectionStart() == token.source_start
    assert box.textCursor().selectionEnd() == token.source_end


def test_projection_selection_copy_of_literal_parenthetical_text_returns_escaped_source(
    widgets: list[QWidget],
) -> None:
    """Copy should preserve raw stored escapes even when projected text hides them."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text=r"painting \(medium\)",
        width=220,
    )
    cursor = box.textCursor()
    cursor.setPosition(0, QTextCursor.MoveMode.MoveAnchor)
    cursor.setPosition(len(box.toPlainText()), QTextCursor.MoveMode.KeepAnchor)
    box.setTextCursor(cursor)
    process_events(app)
    box.copy()

    clipboard = QApplication.clipboard()
    assert clipboard.text() == r"painting \(medium\)"
    assert box.textCursor().selectedText() == r"painting \(medium\)"


def test_projection_selection_double_click_selects_the_whole_plain_tag(
    widgets: list[QWidget],
) -> None:
    """Double-clicking plain segment text should select the full comma-delimited tag."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="alpha, blue green, gamma",
        width=240,
    )
    segment_text = "blue green"
    segment_start = box.toPlainText().index(segment_text)
    segment_end = segment_start + len(segment_text)
    click_point = _point_for_source_position(box, segment_start + 1, app=app)

    QTest.mouseDClick(
        box.viewport(),
        Qt.MouseButton.LeftButton,
        pos=click_point,
    )
    process_events(app)

    cursor = box.textCursor()
    assert cursor.selectionStart() == segment_start
    assert cursor.selectionEnd() == segment_end
    assert cursor.selectedText() == segment_text


def test_projection_selection_double_click_keeps_editor_active_after_segment_selection(
    widgets: list[QWidget],
) -> None:
    """Keep the host editor active after double-clicking one plain-text segment."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="alpha, blue green, gamma",
        width=240,
    )
    segment_text = "blue green"
    segment_start = box.toPlainText().index(segment_text)
    segment_end = segment_start + len(segment_text)
    click_point = _point_for_source_position(box, segment_start + 1, app=app)

    surface = surface_for(box)
    assert app.focusWidget() is surface
    assert surface.hasFocus() is True

    QTest.mouseDClick(
        box.viewport(),
        Qt.MouseButton.LeftButton,
        pos=click_point,
    )
    process_events(app)

    cursor = box.textCursor()
    assert cursor.selectionStart() == segment_start
    assert cursor.selectionEnd() == segment_end
    assert cursor.selectedText() == segment_text
    assert app.focusWidget() is surface
    assert surface.hasFocus() is True


def test_projection_selection_click_after_double_click_refines_to_clicked_word(
    widgets: list[QWidget],
) -> None:
    """A follow-up click after segment selection should refine the highlight to one word."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="alpha, blue green, gamma",
        width=240,
    )
    word_text = "green"
    word_start = box.toPlainText().index(word_text)
    word_end = word_start + len(word_text)
    click_point = _point_for_source_position(box, word_start + 1, app=app)

    QTest.mouseDClick(
        box.viewport(),
        Qt.MouseButton.LeftButton,
        pos=click_point,
    )
    process_events(app)
    QTest.mouseClick(
        box.viewport(),
        Qt.MouseButton.LeftButton,
        pos=click_point,
    )
    process_events(app)

    cursor = box.textCursor()
    assert cursor.selectionStart() == word_start
    assert cursor.selectionEnd() == word_end
    assert cursor.selectedText() == word_text

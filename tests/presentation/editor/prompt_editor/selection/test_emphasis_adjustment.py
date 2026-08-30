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

"""Verify selection-driven emphasis adjustment sessions."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent, QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretPlacement,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptTransientNeutralEmphasisOwner,
)
from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
    process_events,
    projection_paint_state_for,
    show_prompt_editor,
    surface_for,
)
from tests.presentation.editor.prompt_editor.selection.support import (
    _first_emphasis_token,
)


def test_projection_selection_ctrl_up_wraps_the_entire_manual_multiword_selection(
    widgets: list[QWidget],
) -> None:
    """Ctrl+Up should emphasize the full selection without leaving the content highlighted."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="blue green red",
        width=240,
    )
    cursor = box.textCursor()
    cursor.setPosition(0, QTextCursor.MoveMode.MoveAnchor)
    cursor.setPosition(10, QTextCursor.MoveMode.KeepAnchor)
    box.setTextCursor(cursor)
    process_events(app)

    QTest.keyClick(
        surface_for(box),
        Qt.Key.Key_Up,
        Qt.KeyboardModifier.ControlModifier,
    )
    process_events(app)

    cursor = box.textCursor()
    token = _first_emphasis_token(box)
    assert box.toPlainText() == "(blue green:1.05) red"
    assert cursor.selectionStart() == 11
    assert cursor.selectionEnd() == 11
    assert projection_paint_state_for(box).is_token_decoration_accented(token.token_id)
    surface_for(box)._emphasis_feedback_timer.timeout.emit()  # noqa: SLF001
    process_events(app)
    assert not projection_paint_state_for(box).is_token_decoration_accented(
        token.token_id
    )


def test_prompt_editor_keypress_mutes_autocomplete_after_accepted_ctrl_arrow(
    widgets: list[QWidget],
) -> None:
    """Ctrl-arrow emphasis shortcuts should not run post-key autocomplete routing."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="blue green red",
        width=240,
    )
    cursor = box.textCursor()
    cursor.setPosition(0, QTextCursor.MoveMode.MoveAnchor)
    cursor.setPosition(10, QTextCursor.MoveMode.KeepAnchor)
    box.setTextCursor(cursor)
    process_events(app)
    post_key_events: list[QKeyEvent] = []

    def handle_post_key_press_double(event: QKeyEvent) -> None:
        post_key_events.append(event)

    cast(
        Any, box
    )._interaction_controller.handle_post_key_press = handle_post_key_press_double
    event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_Up,
        Qt.KeyboardModifier.ControlModifier,
    )

    box.keyPressEvent(event)
    process_events(app)

    assert box.toPlainText() == "(blue green:1.05) red"
    assert event.isAccepted() is True
    assert post_key_events == []


def test_projection_selection_ctrl_down_adjusts_existing_emphasis_when_surface_receives_the_key(
    widgets: list[QWidget],
) -> None:
    """Ctrl+Down should adjust emphasis without leaving the content selected afterward."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(blue green:1.10) red",
        width=240,
    )
    cursor = box.textCursor()
    cursor.setPosition(1, QTextCursor.MoveMode.MoveAnchor)
    cursor.setPosition(11, QTextCursor.MoveMode.KeepAnchor)
    box.setTextCursor(cursor)
    process_events(app)

    QTest.keyClick(
        surface_for(box),
        Qt.Key.Key_Down,
        Qt.KeyboardModifier.ControlModifier,
    )
    process_events(app)

    cursor = box.textCursor()
    token = _first_emphasis_token(box)
    assert box.toPlainText() == "(blue green:1.05) red"
    assert cursor.selectionStart() == 11
    assert cursor.selectionEnd() == 11
    assert projection_paint_state_for(box).is_token_decoration_accented(token.token_id)
    surface_for(box)._emphasis_feedback_timer.timeout.emit()  # noqa: SLF001
    process_events(app)
    assert not projection_paint_state_for(box).is_token_decoration_accented(
        token.token_id
    )


def test_projection_selection_ctrl_down_crosses_zero_into_negative_emphasis(
    widgets: list[QWidget],
) -> None:
    """Ctrl+Down should move zero emphasis to the next negative step."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:0.00), dog",
        width=220,
    )
    cursor = box.textCursor()
    cursor.setPosition(1, QTextCursor.MoveMode.MoveAnchor)
    cursor.setPosition(4, QTextCursor.MoveMode.KeepAnchor)
    box.setTextCursor(cursor)
    process_events(app)

    QTest.keyClick(
        surface_for(box),
        Qt.Key.Key_Down,
        Qt.KeyboardModifier.ControlModifier,
    )
    process_events(app)

    assert box.toPlainText() == "(cat:-0.05), dog"
    assert _first_emphasis_token(box).value_text == "-0.05"


def test_projection_selection_ctrl_down_can_continue_below_transient_neutral_emphasis(
    widgets: list[QWidget],
) -> None:
    """Ctrl+Down should continue through visible neutral emphasis after unwrap."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), dog",
        width=220,
    )
    cursor = box.textCursor()
    cursor.setPosition(1, QTextCursor.MoveMode.MoveAnchor)
    cursor.setPosition(4, QTextCursor.MoveMode.KeepAnchor)
    box.setTextCursor(cursor)
    process_events(app)

    QTest.keyClick(
        surface_for(box),
        Qt.Key.Key_Down,
        Qt.KeyboardModifier.ControlModifier,
    )
    process_events(app)
    assert box.toPlainText() == "cat, dog"

    QTest.keyClick(
        surface_for(box),
        Qt.Key.Key_Down,
        Qt.KeyboardModifier.ControlModifier,
    )
    process_events(app)

    assert box.toPlainText() == "(cat:0.95), dog"


def test_projection_selection_ctrl_hold_keeps_transient_neutral_visible_until_release(
    widgets: list[QWidget],
) -> None:
    """Holding Ctrl should keep the keyboard-owned neutral shell visible through the neutral step."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), dog",
        width=220,
    )
    cursor = box.textCursor()
    cursor.setPosition(1, QTextCursor.MoveMode.MoveAnchor)
    cursor.setPosition(4, QTextCursor.MoveMode.KeepAnchor)
    box.setTextCursor(cursor)
    process_events(app)

    QTest.keyPress(box, Qt.Key.Key_Control)
    box.modify_emphasis(-0.05)
    process_events(app)

    assert box.toPlainText() == "cat, dog"
    assert box.transient_neutral_emphasis_range() == (0, 3)
    assert (
        box.transient_neutral_emphasis_owner()
        is PromptTransientNeutralEmphasisOwner.KEYBOARD
    )

    QTest.keyRelease(box, Qt.Key.Key_Control)
    process_events(app)

    assert box.transient_neutral_emphasis_range() is None


def test_projection_selection_ctrl_down_keeps_caret_at_transient_content_end(
    widgets: list[QWidget],
) -> None:
    """Ctrl+Down to neutral should keep the caret at the transient token content edge."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), dog",
        width=220,
    )
    surface = surface_for(box)
    cursor = box.textCursor()
    cursor.setPosition(1, QTextCursor.MoveMode.MoveAnchor)
    cursor.setPosition(4, QTextCursor.MoveMode.KeepAnchor)
    box.setTextCursor(cursor)
    process_events(app)

    box.modify_emphasis(-0.05)
    process_events(app)

    focused_token = surface.focused_token()
    assert focused_token is not None
    assert focused_token.synthetic is True
    assert (
        surface._cursor_state.placement is PromptProjectionCaretPlacement.TOKEN_CONTENT
    )
    assert surface._cursor_state.token_id == focused_token.token_id
    assert surface._cursor_state.token_slot == 3


def test_projection_selection_ctrl_session_keeps_caret_at_transient_content_end(
    widgets: list[QWidget],
) -> None:
    """A continued Ctrl session should preserve the content-end caret through neutral unwrap."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="cat, dog",
        width=220,
    )
    surface = surface_for(box)
    cursor = box.textCursor()
    cursor.setPosition(0, QTextCursor.MoveMode.MoveAnchor)
    cursor.setPosition(3, QTextCursor.MoveMode.KeepAnchor)
    box.setTextCursor(cursor)
    process_events(app)

    box.keyPressEvent(
        QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_Up,
            Qt.KeyboardModifier.ControlModifier,
            "",
        )
    )
    process_events(app)
    box.keyPressEvent(
        QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_Down,
            Qt.KeyboardModifier.ControlModifier,
            "",
        )
    )
    process_events(app)

    focused_token = surface.focused_token()
    assert focused_token is not None
    assert focused_token.synthetic is True
    assert (
        surface._cursor_state.placement is PromptProjectionCaretPlacement.TOKEN_CONTENT
    )
    assert surface._cursor_state.token_id == focused_token.token_id
    assert surface._cursor_state.token_slot == 3


def test_projection_selection_ctrl_up_can_restore_emphasis_from_transient_neutral(
    widgets: list[QWidget],
) -> None:
    """Ctrl+Up should restore positive emphasis from visible transient neutral state."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), dog",
        width=220,
    )
    cursor = box.textCursor()
    cursor.setPosition(1, QTextCursor.MoveMode.MoveAnchor)
    cursor.setPosition(4, QTextCursor.MoveMode.KeepAnchor)
    box.setTextCursor(cursor)
    process_events(app)

    QTest.keyClick(
        surface_for(box),
        Qt.Key.Key_Down,
        Qt.KeyboardModifier.ControlModifier,
    )
    process_events(app)
    assert box.toPlainText() == "cat, dog"

    QTest.keyClick(
        surface_for(box),
        Qt.Key.Key_Up,
        Qt.KeyboardModifier.ControlModifier,
    )
    process_events(app)

    assert box.toPlainText() == "(cat:1.05), dog"

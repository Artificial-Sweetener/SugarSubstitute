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

"""Contract tests for token-aware selection and clipboard behavior."""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QFont, QKeyEvent, QPalette, QTextCursor, QTextOption
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QTextEdit, QWidget

from substitute.application.ports import PromptWildcardResolution
from substitute.application.prompt_editor import PromptSyntaxSpanView
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptTransientNeutralEmphasisOwner,
)
from substitute.presentation.editor.prompt_editor.projection.model import (
    PromptProjectionCaretPlacement,
)
from substitute.presentation.editor.prompt_editor.projection.model import (
    PromptProjectionToken,
    PromptProjectionTokenKind,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from tests.prompt_projection_test_helpers import (
    StaticPromptWildcardCatalogGateway,
    ensure_qapp,
    process_events,
    projection_paint_state_for,
    show_prompt_editor,
    surface_for,
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "projection selection tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


@pytest.fixture()
def widgets() -> Iterator[list[QWidget]]:
    """Track widgets created during one projection-selection test."""

    created: list[QWidget] = []
    yield created
    app = ensure_qapp()
    for widget in reversed(created):
        widget.close()
        widget.deleteLater()
    process_events(app)


def _first_emphasis_token(box: PromptEditor) -> PromptProjectionToken:
    """Return the first collapsed emphasis token from one live projection."""

    return next(
        token
        for token in surface_for(box).projection_document().tokens
        if token.kind is PromptProjectionTokenKind.EMPHASIS
    )


def _first_wildcard_token(box: PromptEditor) -> PromptProjectionToken:
    """Return the first collapsed wildcard token from one live projection."""

    return next(
        token
        for token in surface_for(box).projection_document().tokens
        if token.kind is PromptProjectionTokenKind.WILDCARD
    )


def _first_lora_token(box: PromptEditor) -> PromptProjectionToken:
    """Return the first collapsed LoRA token from one live projection."""

    return next(
        token
        for token in surface_for(box).projection_document().tokens
        if token.kind is PromptProjectionTokenKind.LORA
    )


def _set_cursor_position(box: PromptEditor, position: int) -> None:
    """Place the live editor cursor at one raw source position."""

    cursor = box.textCursor()
    cursor.setPosition(position, QTextCursor.MoveMode.MoveAnchor)
    box.setTextCursor(cursor)


def _set_selection_range(
    widget: PromptEditor | QTextEdit,
    *,
    anchor_position: int,
    cursor_position: int,
) -> None:
    """Apply one source-backed selection with explicit anchor and cursor positions."""

    cursor = widget.textCursor()
    cursor.setPosition(anchor_position, QTextCursor.MoveMode.MoveAnchor)
    cursor.setPosition(cursor_position, QTextCursor.MoveMode.KeepAnchor)
    widget.setTextCursor(cursor)


def _show_reference_text_edit(
    widgets: list[QWidget],
    *,
    text: str,
    width: int,
    height: int = 340,
    font: QFont | None = None,
) -> QTextEdit:
    """Create one plain Qt multiline editor used as the caret-navigation reference."""

    reference = QTextEdit()
    reference.resize(width, height)
    if font is not None:
        reference.setFont(font)
    reference.document().setDocumentMargin(4.0)
    text_option = reference.document().defaultTextOption()
    text_option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
    reference.document().setDefaultTextOption(text_option)
    reference.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
    reference.setPlainText(text)
    reference.show()
    reference.setFocus()
    widgets.append(reference)
    return reference


def _set_reference_cursor_position(reference: QTextEdit, position: int) -> None:
    """Place one reference QTextEdit cursor at the supplied raw source position."""

    cursor = reference.textCursor()
    cursor.setPosition(position, QTextCursor.MoveMode.MoveAnchor)
    reference.setTextCursor(cursor)


def _reference_visual_lines(
    reference: QTextEdit,
    *,
    text: str,
    app: QApplication,
) -> tuple[tuple[int, ...], ...]:
    """Return raw source positions grouped by the visual line Qt assigns them to."""

    line_positions: list[list[int]] = []
    current_line: list[int] = []
    previous_y: int | None = None
    for position in range(len(text) + 1):
        _set_reference_cursor_position(reference, position)
        process_events(app)
        cursor_y = reference.cursorRect().center().y()
        if previous_y is None or abs(cursor_y - previous_y) <= 1:
            current_line.append(position)
        else:
            line_positions.append(current_line)
            current_line = [position]
        previous_y = cursor_y
    line_positions.append(current_line)
    return tuple(tuple(line) for line in line_positions)


def _reference_click_point_for_position(
    reference: QTextEdit,
    position: int,
    *,
    app: QApplication,
    x_offset: int | None = None,
) -> QPoint:
    """Return one viewport-local click point aligned with the supplied reference position."""

    _set_reference_cursor_position(reference, position)
    process_events(app)
    rect = reference.cursorRect()
    x_position = rect.center().x() if x_offset is None else x_offset
    return QPoint(x_position, rect.center().y())


def _stable_reference_click_point_for_position(
    reference: QTextEdit,
    position: int,
    *,
    app: QApplication,
    x_offset: int | None = None,
) -> QPoint:
    """Return one reference click point without mutating the live cursor or scroll state."""

    previous_cursor = reference.textCursor()
    previous_scroll = reference.verticalScrollBar().value()
    try:
        return _reference_click_point_for_position(
            reference,
            position,
            app=app,
            x_offset=x_offset,
        )
    finally:
        reference.setTextCursor(previous_cursor)
        reference.verticalScrollBar().setValue(previous_scroll)
        process_events(app)


def _projection_visual_lines(
    box: PromptEditor,
    *,
    text: str,
    app: QApplication,
) -> tuple[tuple[int, ...], ...]:
    """Return raw source positions grouped by the prompt editor's visible rows."""

    surface = surface_for(box)
    previous_cursor_position = surface.cursor_position
    previous_anchor_position = surface.anchor_position
    previous_scroll = box.verticalScrollBar().value()
    line_positions: list[list[int]] = []
    current_line: list[int] = []
    previous_y: int | None = None
    try:
        for position in range(len(text) + 1):
            _set_cursor_position(box, position)
            process_events(app)
            cursor_y = box.cursorRect().center().y()
            if previous_y is None or abs(cursor_y - previous_y) <= 1:
                current_line.append(position)
            else:
                line_positions.append(current_line)
                current_line = [position]
            previous_y = cursor_y
    finally:
        surface.set_cursor_positions(
            cursor_position=previous_cursor_position,
            anchor_position=previous_anchor_position,
        )
        box.verticalScrollBar().setValue(previous_scroll)
        process_events(app)
    line_positions.append(current_line)
    return tuple(tuple(line) for line in line_positions)


def _stable_projection_click_point_for_position(
    box: PromptEditor,
    position: int,
    *,
    app: QApplication,
    x_offset: int | None = None,
) -> QPoint:
    """Return one prompt-editor click point without mutating the live cursor or scroll."""

    surface = surface_for(box)
    previous_cursor_position = surface.cursor_position
    previous_anchor_position = surface.anchor_position
    previous_scroll = box.verticalScrollBar().value()
    measured_point: QPoint | None = None
    try:
        point = _point_for_source_position(box, position, app=app)
        x_position = point.x() if x_offset is None else x_offset
        measured_point = QPoint(x_position, point.y())
    finally:
        surface.set_cursor_positions(
            cursor_position=previous_cursor_position,
            anchor_position=previous_anchor_position,
        )
        box.verticalScrollBar().setValue(previous_scroll)
        process_events(app)
    assert measured_point is not None
    return measured_point


def _drag_select(widget: QWidget, *, start: QPoint, end: QPoint) -> None:
    """Perform one press-drag-release selection gesture inside one widget."""

    QTest.mousePress(
        widget,
        Qt.MouseButton.LeftButton,
        pos=start,
    )
    QTest.mouseMove(widget, end, 10)
    QTest.mouseRelease(
        widget,
        Qt.MouseButton.LeftButton,
        pos=end,
        delay=10,
    )


def _line_interior_position(line: tuple[int, ...]) -> int:
    """Return one non-leading boundary from a visual line when one exists."""

    return line[min(1, len(line) - 1)]


def _selection_bounds(widget: PromptEditor | QTextEdit) -> tuple[int, int, int]:
    """Return one widget's cursor position and source-backed selection bounds."""

    cursor = widget.textCursor()
    return (
        cursor.position(),
        cursor.selectionStart(),
        cursor.selectionEnd(),
    )


def _assert_selection_matches_reference(
    box: PromptEditor,
    reference: QTextEdit,
) -> None:
    """Assert that the prompt editor selection matches the Qt reference widget."""

    assert _selection_bounds(box) == _selection_bounds(reference)


def _drive_vertical_key_on_both(
    box: PromptEditor,
    reference: QTextEdit,
    *,
    key: Qt.Key,
    modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
    app: QApplication,
) -> None:
    """Apply one vertical-navigation keypress to both editors and flush Qt events."""

    QTest.keyClick(box, key, modifiers)
    QTest.keyClick(reference, key, modifiers)
    process_events(app)


def _point_for_source_position(
    box: PromptEditor,
    position: int,
    *,
    app: QApplication,
) -> QPoint:
    """Return one viewport-local click point aligned with the supplied source position."""

    _set_cursor_position(box, position)
    process_events(app)
    return cast(QPoint, box.cursorRect().center())


def test_projection_selection_arrow_keys_walk_visible_emphasis_content_boundaries(
    widgets: list[QWidget],
) -> None:
    """Right-arrow movement should traverse collapsed emphasis content one step at a time."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), suffix",
        width=220,
    )
    token = _first_emphasis_token(box)
    assert token.content_start is not None
    assert token.content_end is not None

    _set_cursor_position(box, token.source_start)
    process_events(app)

    expected_positions = [
        token.content_start,
        token.content_start + 1,
        token.content_start + 2,
        token.content_end,
        token.source_end,
    ]
    observed_positions: list[int] = []

    for _ in expected_positions:
        QTest.keyClick(box, Qt.Key.Key_Right)
        process_events(app)
        observed_positions.append(box.textCursor().position())

    assert observed_positions == expected_positions


def test_projection_selection_shift_arrow_selects_partial_collapsed_emphasis_content(
    widgets: list[QWidget],
) -> None:
    """Shift+arrow should select visible emphasis content instead of the whole token."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), suffix",
        width=220,
    )
    token = _first_emphasis_token(box)
    assert token.content_start is not None

    _set_cursor_position(box, token.content_start)
    process_events(app)

    QTest.keyClick(box, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)
    QTest.keyClick(box, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)
    process_events(app)

    cursor = box.textCursor()
    assert cursor.selectionStart() == token.content_start
    assert cursor.selectionEnd() == token.content_start + 2
    assert cursor.selectedText() == "ca"


def test_projection_selection_left_from_forward_selection_matches_qt_reference(
    widgets: list[QWidget],
) -> None:
    """Left should collapse the selection to its normalized start."""

    app = ensure_qapp()
    text = "alpha beta gamma"
    box = show_prompt_editor(widgets, text=text, width=220)
    reference = _show_reference_text_edit(
        widgets,
        text=text,
        width=box.viewport().width(),
        font=box.font(),
    )

    _set_selection_range(box, anchor_position=6, cursor_position=10)
    _set_reference_cursor_position(reference, 6)
    process_events(app)

    QTest.keyClick(box, Qt.Key.Key_Left)
    process_events(app)

    assert _selection_bounds(box) == _selection_bounds(reference)


def test_projection_selection_right_from_backward_selection_matches_qt_reference(
    widgets: list[QWidget],
) -> None:
    """Right should collapse the selection to its normalized end."""

    app = ensure_qapp()
    text = "alpha beta gamma"
    box = show_prompt_editor(widgets, text=text, width=220)
    reference = _show_reference_text_edit(
        widgets,
        text=text,
        width=box.viewport().width(),
        font=box.font(),
    )

    _set_selection_range(box, anchor_position=10, cursor_position=6)
    _set_reference_cursor_position(reference, 10)
    process_events(app)

    QTest.keyClick(box, Qt.Key.Key_Right)
    process_events(app)

    assert _selection_bounds(box) == _selection_bounds(reference)


def test_projection_selection_up_from_forward_wrapped_selection_matches_qt_reference(
    widgets: list[QWidget],
) -> None:
    """Up should move as if the caret had started at the selection start."""

    app = ensure_qapp()
    text = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda"
    box = show_prompt_editor(widgets, text=text, width=140)
    reference = _show_reference_text_edit(
        widgets,
        text=text,
        width=box.viewport().width(),
        font=box.font(),
    )
    visual_lines = _reference_visual_lines(reference, text=text, app=app)
    start_position = _line_interior_position(visual_lines[1])
    end_position = _line_interior_position(visual_lines[2])

    _set_selection_range(
        box,
        anchor_position=start_position,
        cursor_position=end_position,
    )
    _set_selection_range(
        reference,
        anchor_position=start_position,
        cursor_position=start_position,
    )
    process_events(app)

    QTest.keyClick(box, Qt.Key.Key_Up)
    QTest.keyClick(reference, Qt.Key.Key_Up)
    process_events(app)

    assert _selection_bounds(box) == _selection_bounds(reference)


def test_projection_selection_down_from_backward_wrapped_selection_matches_qt_reference(
    widgets: list[QWidget],
) -> None:
    """Down should move as if the caret had started at the selection end."""

    app = ensure_qapp()
    text = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda"
    box = show_prompt_editor(widgets, text=text, width=140)
    reference = _show_reference_text_edit(
        widgets,
        text=text,
        width=box.viewport().width(),
        font=box.font(),
    )
    visual_lines = _reference_visual_lines(reference, text=text, app=app)
    earlier_position = _line_interior_position(visual_lines[1])
    later_position = _line_interior_position(visual_lines[2])

    _set_selection_range(
        box,
        anchor_position=later_position,
        cursor_position=earlier_position,
    )
    _set_selection_range(
        reference,
        anchor_position=later_position,
        cursor_position=later_position,
    )
    process_events(app)

    QTest.keyClick(box, Qt.Key.Key_Down)
    QTest.keyClick(reference, Qt.Key.Key_Down)
    process_events(app)

    assert _selection_bounds(box) == _selection_bounds(reference)


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
    QTest.qWait(260)
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
    QTest.qWait(260)
    process_events(app)
    assert not projection_paint_state_for(box).is_token_decoration_accented(
        token.token_id
    )


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


def test_projection_selection_wildcards_remain_atomic_for_arrow_navigation(
    widgets: list[QWidget],
) -> None:
    """Wildcard tokens should still move from before to after in one step."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="{animal}, suffix",
        width=220,
        wildcard_gateway=StaticPromptWildcardCatalogGateway(
            {
                ("animal", "simple", None): PromptWildcardResolution(
                    identifier="animal",
                    wildcard_form="simple",
                    exists=True,
                ),
            }
        ),
    )
    token = _first_wildcard_token(box)

    _set_cursor_position(box, token.source_start)
    process_events(app)
    QTest.keyClick(box, Qt.Key.Key_Right)
    process_events(app)

    assert box.textCursor().position() == token.source_end


def test_projection_selection_down_matches_qt_from_middle_of_wrapped_plain_text_line(
    widgets: list[QWidget],
) -> None:
    """Down should land on the same source position Qt chooses for wrapped plain text."""

    app = ensure_qapp()
    text = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda"
    box = show_prompt_editor(widgets, text=text, width=140)
    reference = _show_reference_text_edit(
        widgets,
        text=text,
        width=box.viewport().width(),
        font=box.font(),
    )
    visual_lines = _reference_visual_lines(reference, text=text, app=app)
    starting_line = next(line for line in visual_lines if len(line) >= 5)
    starting_position = starting_line[len(starting_line) // 2]

    _set_cursor_position(box, starting_position)
    _set_reference_cursor_position(reference, starting_position)
    process_events(app)

    _drive_vertical_key_on_both(
        box,
        reference,
        key=Qt.Key.Key_Down,
        app=app,
    )

    assert box.textCursor().position() == reference.textCursor().position()


def test_projection_selection_down_matches_qt_near_wrapped_line_end_with_shorter_successor(
    widgets: list[QWidget],
) -> None:
    """Down should choose the same shorter-line fallback position Qt chooses."""

    app = ensure_qapp()
    text = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda"
    box = show_prompt_editor(widgets, text=text, width=140)
    reference = _show_reference_text_edit(
        widgets,
        text=text,
        width=box.viewport().width(),
        font=box.font(),
    )
    visual_lines = _reference_visual_lines(reference, text=text, app=app)
    source_line = next(
        visual_lines[index]
        for index in range(len(visual_lines) - 1)
        if len(visual_lines[index]) >= 4
        and len(visual_lines[index + 1]) < len(visual_lines[index])
    )
    starting_position = source_line[-2]

    _set_cursor_position(box, starting_position)
    _set_reference_cursor_position(reference, starting_position)
    process_events(app)

    _drive_vertical_key_on_both(
        box,
        reference,
        key=Qt.Key.Key_Down,
        app=app,
    )

    assert box.textCursor().position() == reference.textCursor().position()


def test_projection_selection_up_matches_qt_from_wrapped_plain_text_line(
    widgets: list[QWidget],
) -> None:
    """Up should land on the same wrapped-line source position Qt chooses."""

    app = ensure_qapp()
    text = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda"
    box = show_prompt_editor(widgets, text=text, width=140)
    reference = _show_reference_text_edit(
        widgets,
        text=text,
        width=box.viewport().width(),
        font=box.font(),
    )
    visual_lines = _reference_visual_lines(reference, text=text, app=app)
    starting_line = next(line for line in visual_lines[1:] if len(line) >= 4)
    starting_position = starting_line[len(starting_line) // 2]

    _set_cursor_position(box, starting_position)
    _set_reference_cursor_position(reference, starting_position)
    process_events(app)

    _drive_vertical_key_on_both(
        box,
        reference,
        key=Qt.Key.Key_Up,
        app=app,
    )

    assert box.textCursor().position() == reference.textCursor().position()


def test_projection_selection_shift_down_matches_qt_selection_extension(
    widgets: list[QWidget],
) -> None:
    """Shift+Down should extend the selection to the same Qt source bounds."""

    app = ensure_qapp()
    text = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda"
    box = show_prompt_editor(widgets, text=text, width=140)
    reference = _show_reference_text_edit(
        widgets,
        text=text,
        width=box.viewport().width(),
        font=box.font(),
    )
    visual_lines = _reference_visual_lines(reference, text=text, app=app)
    starting_line = next(line for line in visual_lines if len(line) >= 5)
    starting_position = starting_line[len(starting_line) // 2]

    _set_cursor_position(box, starting_position)
    _set_reference_cursor_position(reference, starting_position)
    process_events(app)

    _drive_vertical_key_on_both(
        box,
        reference,
        key=Qt.Key.Key_Down,
        modifiers=Qt.KeyboardModifier.ShiftModifier,
        app=app,
    )

    assert box.textCursor().position() == reference.textCursor().position()
    assert box.textCursor().selectionStart() == reference.textCursor().selectionStart()
    assert box.textCursor().selectionEnd() == reference.textCursor().selectionEnd()


def test_projection_selection_shift_up_matches_qt_selection_extension(
    widgets: list[QWidget],
) -> None:
    """Shift+Up should preserve the same anchor and selection bounds as Qt."""

    app = ensure_qapp()
    text = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda"
    box = show_prompt_editor(widgets, text=text, width=140)
    reference = _show_reference_text_edit(
        widgets,
        text=text,
        width=box.viewport().width(),
        font=box.font(),
    )
    visual_lines = _reference_visual_lines(reference, text=text, app=app)
    starting_line = next(line for line in visual_lines[1:] if len(line) >= 4)
    starting_position = starting_line[len(starting_line) // 2]

    _set_cursor_position(box, starting_position)
    _set_reference_cursor_position(reference, starting_position)
    process_events(app)

    _drive_vertical_key_on_both(
        box,
        reference,
        key=Qt.Key.Key_Up,
        modifiers=Qt.KeyboardModifier.ShiftModifier,
        app=app,
    )

    assert box.textCursor().position() == reference.textCursor().position()
    assert box.textCursor().selectionStart() == reference.textCursor().selectionStart()
    assert box.textCursor().selectionEnd() == reference.textCursor().selectionEnd()


def test_projection_selection_repeated_down_matches_qt_preferred_column_behavior(
    widgets: list[QWidget],
) -> None:
    """Repeated Down presses should preserve the same preferred column Qt preserves."""

    app = ensure_qapp()
    text = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda"
    box = show_prompt_editor(widgets, text=text, width=140)
    reference = _show_reference_text_edit(
        widgets,
        text=text,
        width=box.viewport().width(),
        font=box.font(),
    )
    visual_lines = _reference_visual_lines(reference, text=text, app=app)
    starting_line = next(line for line in visual_lines if len(line) >= 5)
    starting_position = starting_line[len(starting_line) // 2]

    _set_cursor_position(box, starting_position)
    _set_reference_cursor_position(reference, starting_position)
    process_events(app)

    for _ in range(3):
        _drive_vertical_key_on_both(
            box,
            reference,
            key=Qt.Key.Key_Down,
            app=app,
        )

    assert box.textCursor().position() == reference.textCursor().position()


def test_projection_selection_blank_lines_match_qt_vertical_navigation(
    widgets: list[QWidget],
) -> None:
    """Down should keep blank lines reachable at the same source positions as Qt."""

    app = ensure_qapp()
    text = "alpha\n\n\nbeta gamma"
    box = show_prompt_editor(widgets, text=text, width=180)
    reference = _show_reference_text_edit(
        widgets,
        text=text,
        width=box.viewport().width(),
        font=box.font(),
    )
    starting_position = text.index("p")

    _set_cursor_position(box, starting_position)
    _set_reference_cursor_position(reference, starting_position)
    process_events(app)

    for _ in range(3):
        _drive_vertical_key_on_both(
            box,
            reference,
            key=Qt.Key.Key_Down,
            app=app,
        )
        assert box.textCursor().position() == reference.textCursor().position()


def test_projection_selection_blank_line_clicks_match_qt_reference(
    widgets: list[QWidget],
) -> None:
    """Clicking blank visual lines should land on the same source positions Qt chooses."""

    app = ensure_qapp()
    text = "alpha\n\n\nbeta gamma"
    box = show_prompt_editor(widgets, text=text, width=180)
    reference = _show_reference_text_edit(
        widgets,
        text=text,
        width=box.viewport().width(),
        font=box.font(),
    )
    visual_lines = _reference_visual_lines(reference, text=text, app=app)
    assert len(visual_lines) >= 4
    blank_line_position = visual_lines[1][0]

    for x_offset in (4, box.viewport().width() // 2, box.viewport().width() - 4):
        click_point = _reference_click_point_for_position(
            reference,
            blank_line_position,
            app=app,
            x_offset=x_offset,
        )
        QTest.mouseClick(
            box.viewport(),
            Qt.MouseButton.LeftButton,
            pos=click_point,
        )
        QTest.mouseClick(
            reference.viewport(),
            Qt.MouseButton.LeftButton,
            pos=click_point,
        )
        process_events(app)
        assert box.textCursor().position() == reference.textCursor().position()


def test_projection_selection_drag_through_blank_lines_matches_qt_reference(
    widgets: list[QWidget],
) -> None:
    """Dragging selection through blank visual lines should track the same active end as Qt."""

    app = ensure_qapp()
    text = "alpha\n\n\nbeta gamma"
    box = show_prompt_editor(widgets, text=text, width=180)
    reference = _show_reference_text_edit(
        widgets,
        text=text,
        width=box.viewport().width(),
        font=box.font(),
    )
    visual_lines = _reference_visual_lines(reference, text=text, app=app)
    start_position = text.index("p")
    blank_line_position = visual_lines[2][0]
    start_point = _reference_click_point_for_position(
        reference, start_position, app=app
    )
    blank_line_point = _reference_click_point_for_position(
        reference,
        blank_line_position,
        app=app,
        x_offset=box.viewport().width() - 6,
    )

    _drag_select(box.viewport(), start=start_point, end=blank_line_point)
    _drag_select(reference.viewport(), start=start_point, end=blank_line_point)
    process_events(app)

    _assert_selection_matches_reference(box, reference)


def test_projection_selection_paints_selected_empty_lines_for_clarity(
    widgets: list[QWidget],
) -> None:
    """Selecting one blank line break should visibly paint the empty visual row."""

    app = ensure_qapp()
    box = show_prompt_editor(widgets, text="alpha\n\nbeta", width=180)
    cursor = box.textCursor()
    cursor.setPosition(6, QTextCursor.MoveMode.MoveAnchor)
    cursor.setPosition(7, QTextCursor.MoveMode.KeepAnchor)
    box.setTextCursor(cursor)
    process_events(app)

    surface = surface_for(box)
    blank_line = next(
        line
        for line in surface._layout._snapshot.lines
        if not line.fragments  # noqa: SLF001
    )
    selection_rects = surface._layout.selection_rects(surface._selection())  # noqa: SLF001
    blank_line_rect = next(
        rect for rect in selection_rects if abs(rect.top() - blank_line.top) < 1.0
    )

    sample_point = QPoint(
        int(blank_line_rect.left() + 1.0),
        int(blank_line_rect.top() + 1.0),
    )
    image = box.viewport().grab().toImage()

    assert image.pixelColor(sample_point) == box.palette().color(
        QPalette.ColorRole.Highlight
    )


def test_projection_selection_shift_up_from_empty_line_paints_one_break_marker(
    widgets: list[QWidget],
) -> None:
    """Shift+Up from an empty line should paint only the selected line break."""

    app = ensure_qapp()
    box = show_prompt_editor(widgets, text="\n\n", width=180)
    cursor = box.textCursor()
    cursor.setPosition(1, QTextCursor.MoveMode.MoveAnchor)
    box.setTextCursor(cursor)
    box.setFocus()
    process_events(app)

    QTest.keyClick(box, Qt.Key.Key_Up, Qt.KeyboardModifier.ShiftModifier)
    process_events(app)

    surface = surface_for(box)
    selection_rects = surface._layout.selection_rects(surface._selection())  # noqa: SLF001
    painted_line_tops = {
        round(rect.top(), 1) for rect in selection_rects if rect.width() >= 8.0
    }

    assert box.textCursor().selectedText() == "\n"
    assert len(painted_line_tops) == 1
    assert painted_line_tops == {round(surface._layout._snapshot.lines[0].top, 1)}  # noqa: SLF001


def test_projection_selection_does_not_paint_blank_line_above_next_line_selection(
    widgets: list[QWidget],
) -> None:
    """Selecting a line from column 0 should not also highlight the empty line above it."""

    app = ensure_qapp()
    text = "some, prompt, tags,\n\nblue and pink,\n"
    box = show_prompt_editor(widgets, text=text, width=220)
    line_start = text.index("blue and pink")
    line_end = line_start + len("blue and pink")
    cursor = box.textCursor()
    cursor.setPosition(line_start, QTextCursor.MoveMode.MoveAnchor)
    cursor.setPosition(line_end, QTextCursor.MoveMode.KeepAnchor)
    box.setTextCursor(cursor)
    process_events(app)

    surface = surface_for(box)
    selection_rects = surface._layout.selection_rects(surface._selection())  # noqa: SLF001
    empty_line = next(
        line
        for line in surface._layout._snapshot.lines
        if not line.fragments and line.source_start < line_start  # noqa: SLF001
    )

    assert not any(abs(rect.top() - empty_line.top) < 1.0 for rect in selection_rects)


def test_projection_selection_drag_to_same_line_end_excludes_newline(
    widgets: list[QWidget],
) -> None:
    """Dragging to a same-line content end should not secretly select the newline."""

    app = ensure_qapp()
    box = show_prompt_editor(widgets, text="alpha\nbeta", width=180)
    start_point = _stable_projection_click_point_for_position(box, 0, app=app)
    end_point = _stable_projection_click_point_for_position(box, 5, app=app)

    _drag_select(box.viewport(), start=start_point, end=end_point)
    process_events(app)

    assert box.textCursor().selectedText() == "alpha"


def test_projection_selection_drag_to_next_line_start_includes_newline(
    widgets: list[QWidget],
) -> None:
    """Dragging into the next visual line should intentionally select the newline."""

    app = ensure_qapp()
    box = show_prompt_editor(widgets, text="alpha\nbeta", width=180)
    start_point = _stable_projection_click_point_for_position(box, 0, app=app)
    end_point = _stable_projection_click_point_for_position(box, 6, app=app)

    _drag_select(box.viewport(), start=start_point, end=end_point)
    process_events(app)

    assert box.textCursor().selectedText() == "alpha\n"


def test_projection_selection_reverse_drags_handle_newline_boundaries(
    widgets: list[QWidget],
) -> None:
    """Reverse drags should include newlines only when the pointer crosses rows."""

    app = ensure_qapp()
    box = show_prompt_editor(widgets, text="alpha\nbeta", width=180)
    line_end = _stable_projection_click_point_for_position(box, 5, app=app)
    document_start = _stable_projection_click_point_for_position(box, 0, app=app)
    next_line_start = _stable_projection_click_point_for_position(box, 6, app=app)

    _drag_select(box.viewport(), start=line_end, end=document_start)
    process_events(app)
    assert box.textCursor().selectedText() == "alpha"

    _drag_select(box.viewport(), start=next_line_start, end=document_start)
    process_events(app)
    assert box.textCursor().selectedText() == "alpha\n"


def test_projection_selection_paints_empty_line_when_drag_endpoint_lands_on_it(
    widgets: list[QWidget],
) -> None:
    """Dragging onto an empty line should paint that row before advancing past it."""

    app = ensure_qapp()
    box = show_prompt_editor(widgets, text="alpha\n\nbeta", width=180)
    cursor = box.textCursor()
    cursor.setPosition(0, QTextCursor.MoveMode.MoveAnchor)
    cursor.setPosition(6, QTextCursor.MoveMode.KeepAnchor)
    box.setTextCursor(cursor)
    process_events(app)

    surface = surface_for(box)
    blank_line = next(
        line
        for line in surface._layout._snapshot.lines
        if not line.fragments  # noqa: SLF001
    )
    selection_rects = surface._layout.selection_rects(surface._selection())  # noqa: SLF001
    blank_line_rect = next(
        rect for rect in selection_rects if abs(rect.top() - blank_line.top) < 1.0
    )

    sample_point = QPoint(
        int(blank_line_rect.left() + 1.0),
        int(blank_line_rect.top() + 1.0),
    )
    image = box.viewport().grab().toImage()

    assert image.pixelColor(sample_point) == box.palette().color(
        QPalette.ColorRole.Highlight
    )


def test_projection_selection_drag_paints_highlight_before_mouse_release(
    widgets: list[QWidget],
) -> None:
    """Dragging should repaint the visible selection before the mouse button is released."""

    app = ensure_qapp()
    text = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda"
    box = show_prompt_editor(widgets, text=text, width=140)
    reference = _show_reference_text_edit(
        widgets,
        text=text,
        width=box.viewport().width(),
        font=box.font(),
    )
    visual_lines = _reference_visual_lines(reference, text=text, app=app)
    first_line = visual_lines[0]
    second_line = visual_lines[1]
    start_position = first_line[0]
    start_point = _stable_projection_click_point_for_position(
        box,
        start_position,
        app=app,
    )
    target_y = _stable_reference_click_point_for_position(
        reference,
        _line_interior_position(second_line),
        app=app,
    ).y()

    QTest.mousePress(
        box.viewport(),
        Qt.MouseButton.LeftButton,
        pos=start_point,
    )
    QTest.mouseMove(
        box.viewport(),
        QPoint(start_point.x(), target_y),
        10,
    )
    process_events(app)

    surface = surface_for(box)
    selection_rects = surface._layout.selection_rects(surface._selection())
    assert selection_rects
    sample_rect = selection_rects[0].translated(0.0, -surface._scroll_offset())
    sample_point = QPoint(
        int(sample_rect.left() + 1.0),
        int(sample_rect.top() + 1.0),
    )
    image = box.viewport().grab().toImage()
    assert image.pixelColor(sample_point) == box.palette().color(
        QPalette.ColorRole.Highlight
    )

    QTest.mouseRelease(
        box.viewport(),
        Qt.MouseButton.LeftButton,
        pos=QPoint(start_point.x(), target_y),
        delay=10,
    )
    process_events(app)


def test_projection_selection_drag_to_offscreen_last_character_matches_qt_reference(
    widgets: list[QWidget],
) -> None:
    """Dragging toward an offscreen line end should still make the final character reachable."""

    app = ensure_qapp()
    text = (
        "1girl, solo, portrait, looking at viewer, soft lighting,\n\n\n"
        "detailed eyes, pastel colors, clean lineart, highres"
    )
    box = show_prompt_editor(widgets, text=text, width=220)
    reference = _show_reference_text_edit(
        widgets,
        text=text,
        width=box.viewport().width(),
        font=box.font(),
    )
    anchor_position = text.index("detailed")
    final_position = text.rfind("s")
    box_anchor = _stable_projection_click_point_for_position(
        box,
        anchor_position,
        app=app,
    )
    reference_anchor = _stable_reference_click_point_for_position(
        reference,
        anchor_position,
        app=app,
    )
    reference_end_y = _stable_reference_click_point_for_position(
        reference,
        final_position,
        app=app,
    ).y()
    drag_end = QPoint(box.viewport().width() - 2, reference_end_y)

    QTest.mousePress(
        box.viewport(),
        Qt.MouseButton.LeftButton,
        pos=box_anchor,
    )
    QTest.mouseMove(box.viewport(), drag_end, 10)
    process_events(app)

    QTest.mousePress(
        reference.viewport(),
        Qt.MouseButton.LeftButton,
        pos=reference_anchor,
    )
    QTest.mouseMove(reference.viewport(), drag_end, 10)
    process_events(app)

    _assert_selection_matches_reference(box, reference)

    QTest.mouseRelease(
        box.viewport(),
        Qt.MouseButton.LeftButton,
        pos=drag_end,
        delay=10,
    )
    QTest.mouseRelease(
        reference.viewport(),
        Qt.MouseButton.LeftButton,
        pos=drag_end,
        delay=10,
    )
    process_events(app)

    _assert_selection_matches_reference(box, reference)


def test_projection_selection_drag_down_across_wrapped_lines_matches_qt_reference(
    widgets: list[QWidget],
) -> None:
    """Dragging into the next wrapped row should match Qt's row-progression semantics."""

    app = ensure_qapp()
    text = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda"
    box = show_prompt_editor(widgets, text=text, width=140)
    reference = _show_reference_text_edit(
        widgets,
        text=text,
        width=box.viewport().width(),
        font=box.font(),
    )
    visual_lines = _reference_visual_lines(reference, text=text, app=app)
    assert len(visual_lines) >= 2
    first_line = visual_lines[0]
    second_line = visual_lines[1]
    start_position = first_line[0]
    box_start = _stable_projection_click_point_for_position(
        box,
        start_position,
        app=app,
    )
    reference_start = _stable_reference_click_point_for_position(
        reference,
        start_position,
        app=app,
    )
    box_target_y = _stable_projection_click_point_for_position(
        box,
        _line_interior_position(second_line),
        app=app,
    ).y()
    reference_target_y = _stable_reference_click_point_for_position(
        reference,
        _line_interior_position(second_line),
        app=app,
    ).y()
    box_target_y = reference_target_y

    _drag_select(
        box.viewport(),
        start=box_start,
        end=QPoint(box_start.x(), box_target_y),
    )
    _drag_select(
        reference.viewport(),
        start=reference_start,
        end=QPoint(reference_start.x(), reference_target_y),
    )
    process_events(app)

    _assert_selection_matches_reference(box, reference)


def test_projection_selection_drag_up_across_wrapped_lines_matches_qt_reference(
    widgets: list[QWidget],
) -> None:
    """Dragging into the previous wrapped row should preserve the same Qt anchor/end."""

    app = ensure_qapp()
    text = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda"
    box = show_prompt_editor(widgets, text=text, width=140)
    reference = _show_reference_text_edit(
        widgets,
        text=text,
        width=box.viewport().width(),
        font=box.font(),
    )
    visual_lines = _reference_visual_lines(reference, text=text, app=app)
    assert len(visual_lines) >= 2
    first_line = visual_lines[0]
    second_line = visual_lines[1]
    start_position = second_line[min(3, len(second_line) - 1)]
    box_start = _stable_projection_click_point_for_position(
        box,
        start_position,
        app=app,
    )
    reference_start = _stable_reference_click_point_for_position(
        reference,
        start_position,
        app=app,
    )
    box_target_y = _stable_projection_click_point_for_position(
        box,
        _line_interior_position(first_line),
        app=app,
    ).y()
    reference_target_y = _stable_reference_click_point_for_position(
        reference,
        _line_interior_position(first_line),
        app=app,
    ).y()
    box_target_y = reference_target_y

    _drag_select(
        box.viewport(),
        start=box_start,
        end=QPoint(box_start.x(), box_target_y),
    )
    _drag_select(
        reference.viewport(),
        start=reference_start,
        end=QPoint(reference_start.x(), reference_target_y),
    )
    process_events(app)

    _assert_selection_matches_reference(box, reference)


def test_projection_selection_drag_down_across_wrapped_lines_with_short_successor_matches_qt_reference(
    widgets: list[QWidget],
) -> None:
    """Dragging down near a longer row's end should match Qt on a shorter successor row."""

    app = ensure_qapp()
    text = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda"
    box = show_prompt_editor(widgets, text=text, width=140)
    reference = _show_reference_text_edit(
        widgets,
        text=text,
        width=box.viewport().width(),
        font=box.font(),
    )
    visual_lines = _reference_visual_lines(reference, text=text, app=app)
    source_line_index = next(
        index
        for index in range(len(visual_lines) - 1)
        if len(visual_lines[index]) >= 4
        and len(visual_lines[index + 1]) < len(visual_lines[index])
    )
    source_line = visual_lines[source_line_index]
    successor_line = visual_lines[source_line_index + 1]
    start_position = source_line[-2]
    box_start = _stable_projection_click_point_for_position(
        box,
        start_position,
        app=app,
    )
    reference_start = _stable_reference_click_point_for_position(
        reference,
        start_position,
        app=app,
    )
    box_target_y = _stable_projection_click_point_for_position(
        box,
        _line_interior_position(successor_line),
        app=app,
    ).y()
    reference_target_y = _stable_reference_click_point_for_position(
        reference,
        _line_interior_position(successor_line),
        app=app,
    ).y()
    box_target_y = reference_target_y

    _drag_select(
        box.viewport(),
        start=box_start,
        end=QPoint(box_start.x(), box_target_y),
    )
    _drag_select(
        reference.viewport(),
        start=reference_start,
        end=QPoint(reference_start.x(), reference_target_y),
    )
    process_events(app)

    _assert_selection_matches_reference(box, reference)


def test_projection_selection_drag_down_near_wrapped_line_end_matches_qt_reference(
    widgets: list[QWidget],
) -> None:
    """Dragging down from the end of one wrapped row should match Qt's next-row choice."""

    app = ensure_qapp()
    text = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda"
    box = show_prompt_editor(widgets, text=text, width=140)
    reference = _show_reference_text_edit(
        widgets,
        text=text,
        width=box.viewport().width(),
        font=box.font(),
    )
    visual_lines = _reference_visual_lines(reference, text=text, app=app)
    assert len(visual_lines) >= 2
    first_line = visual_lines[0]
    second_line = visual_lines[1]
    start_position = first_line[-1]
    box_start = _stable_projection_click_point_for_position(
        box,
        start_position,
        app=app,
    )
    reference_start = _stable_reference_click_point_for_position(
        reference,
        start_position,
        app=app,
    )
    box_target_y = _stable_projection_click_point_for_position(
        box,
        _line_interior_position(second_line),
        app=app,
    ).y()
    reference_target_y = _stable_reference_click_point_for_position(
        reference,
        _line_interior_position(second_line),
        app=app,
    ).y()
    box_target_y = reference_target_y

    _drag_select(
        box.viewport(),
        start=box_start,
        end=QPoint(box_start.x(), box_target_y),
    )
    _drag_select(
        reference.viewport(),
        start=reference_start,
        end=QPoint(reference_start.x(), reference_target_y),
    )
    process_events(app)

    _assert_selection_matches_reference(box, reference)


def test_projection_selection_drag_up_across_wrapped_lines_with_short_predecessor_matches_qt_reference(
    widgets: list[QWidget],
) -> None:
    """Dragging up from a longer row should match Qt on a shorter predecessor row."""

    app = ensure_qapp()
    text = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda"
    box = show_prompt_editor(widgets, text=text, width=140)
    reference = _show_reference_text_edit(
        widgets,
        text=text,
        width=box.viewport().width(),
        font=box.font(),
    )
    visual_lines = _reference_visual_lines(reference, text=text, app=app)
    source_line_index = next(
        index
        for index in range(1, len(visual_lines))
        if len(visual_lines[index - 1]) < len(visual_lines[index])
        and len(visual_lines[index]) >= 4
    )
    source_line = visual_lines[source_line_index]
    predecessor_line = visual_lines[source_line_index - 1]
    start_position = source_line[-2]
    box_start = _stable_projection_click_point_for_position(
        box,
        start_position,
        app=app,
    )
    reference_start = _stable_reference_click_point_for_position(
        reference,
        start_position,
        app=app,
    )
    box_target_y = _stable_projection_click_point_for_position(
        box,
        _line_interior_position(predecessor_line),
        app=app,
    ).y()
    reference_target_y = _stable_reference_click_point_for_position(
        reference,
        _line_interior_position(predecessor_line),
        app=app,
    ).y()
    box_target_y = reference_target_y

    _drag_select(
        box.viewport(),
        start=box_start,
        end=QPoint(box_start.x(), box_target_y),
    )
    _drag_select(
        reference.viewport(),
        start=reference_start,
        end=QPoint(reference_start.x(), reference_target_y),
    )
    process_events(app)

    _assert_selection_matches_reference(box, reference)


def test_projection_selection_drag_down_from_first_wrapped_line_to_later_row_matches_qt_reference(
    widgets: list[QWidget],
) -> None:
    """Dragging straight down across several wrapped rows should keep progressing like Qt."""

    app = ensure_qapp()
    text = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda"
    box = show_prompt_editor(widgets, text=text, width=140)
    reference = _show_reference_text_edit(
        widgets,
        text=text,
        width=box.viewport().width(),
        font=box.font(),
    )
    visual_lines = _reference_visual_lines(reference, text=text, app=app)
    assert len(visual_lines) >= 9
    start_position = visual_lines[0][0]
    target_line = visual_lines[8]
    box_start = _stable_projection_click_point_for_position(
        box,
        start_position,
        app=app,
    )
    reference_start = _stable_reference_click_point_for_position(
        reference,
        start_position,
        app=app,
    )
    box_target_y = _stable_projection_click_point_for_position(
        box,
        _line_interior_position(target_line),
        app=app,
    ).y()
    reference_target_y = _stable_reference_click_point_for_position(
        reference,
        _line_interior_position(target_line),
        app=app,
    ).y()
    box_target_y = reference_target_y

    _drag_select(
        box.viewport(),
        start=box_start,
        end=QPoint(box_start.x(), box_target_y),
    )
    _drag_select(
        reference.viewport(),
        start=reference_start,
        end=QPoint(reference_start.x(), reference_target_y),
    )
    process_events(app)

    _assert_selection_matches_reference(box, reference)


def test_projection_selection_drag_across_wrapped_lines_with_projected_emphasis_traverses_the_prior_row(
    widgets: list[QWidget],
) -> None:
    """Dragging into the next projected row should fully traverse the prior emphasis row."""

    app = ensure_qapp()
    text = "(alpha beta gamma delta epsilon zeta eta theta iota kappa:1.05) lambda"
    box = show_prompt_editor(widgets, text=text, width=160)
    visual_lines = _projection_visual_lines(box, text=text, app=app)
    assert len(visual_lines) >= 2
    first_line = visual_lines[0]
    second_line = visual_lines[1]
    start_position = first_line[min(2, len(first_line) - 1)]
    start_point = _stable_projection_click_point_for_position(
        box,
        start_position,
        app=app,
    )
    target_y = _stable_projection_click_point_for_position(
        box,
        _line_interior_position(second_line),
        app=app,
    ).y()

    _drag_select(
        box.viewport(),
        start=start_point,
        end=QPoint(start_point.x(), target_y),
    )
    process_events(app)

    cursor = box.textCursor()
    assert cursor.selectionEnd() > cursor.selectionStart()
    assert cursor.selectionStart() <= start_position
    assert cursor.position() >= second_line[0]
    assert cursor.selectionEnd() >= second_line[0]


def test_projection_selection_drag_across_wrapped_lines_with_projected_wildcards_traverses_the_prior_row(
    widgets: list[QWidget],
) -> None:
    """Dragging into the next projected row should keep wildcard rows source-progressive."""

    app = ensure_qapp()
    text = "{animal} alpha beta gamma delta epsilon zeta eta theta iota kappa"
    box = show_prompt_editor(
        widgets,
        text=text,
        width=150,
        wildcard_gateway=StaticPromptWildcardCatalogGateway(
            {
                ("animal", "simple", None): PromptWildcardResolution(
                    identifier="animal",
                    wildcard_form="simple",
                    exists=True,
                ),
            }
        ),
    )
    visual_lines = _projection_visual_lines(box, text=text, app=app)
    assert len(visual_lines) >= 2
    first_line = visual_lines[0]
    second_line = visual_lines[1]
    start_position = first_line[min(2, len(first_line) - 1)]
    start_point = _stable_projection_click_point_for_position(
        box,
        start_position,
        app=app,
    )
    target_y = _stable_projection_click_point_for_position(
        box,
        _line_interior_position(second_line),
        app=app,
    ).y()

    _drag_select(
        box.viewport(),
        start=start_point,
        end=QPoint(start_point.x(), target_y),
    )
    process_events(app)

    cursor = box.textCursor()
    assert cursor.selectionEnd() > cursor.selectionStart()
    assert cursor.selectionStart() <= start_position
    assert cursor.position() >= second_line[0]
    assert cursor.selectionEnd() >= second_line[0]


def test_projection_selection_up_on_first_visual_line_moves_to_first_column(
    widgets: list[QWidget],
) -> None:
    """Up on the first visual line should clamp the caret to that line's first stop."""

    app = ensure_qapp()
    text = "alpha beta gamma delta epsilon zeta eta theta iota"
    box = show_prompt_editor(widgets, text=text, width=140)
    reference = _show_reference_text_edit(
        widgets,
        text=text,
        width=box.viewport().width(),
        font=box.font(),
    )
    visual_lines = _reference_visual_lines(reference, text=text, app=app)
    first_line = visual_lines[0]
    starting_position = first_line[min(len(first_line) - 1, 4)]

    _set_cursor_position(box, starting_position)
    process_events(app)

    QTest.keyClick(box, Qt.Key.Key_Up)
    process_events(app)

    assert box.textCursor().position() == first_line[0]


def test_projection_selection_down_on_last_visual_line_moves_to_last_column(
    widgets: list[QWidget],
) -> None:
    """Down on the last visual line should clamp the caret to that line's last stop."""

    app = ensure_qapp()
    text = "alpha beta gamma delta epsilon zeta eta theta iota"
    box = show_prompt_editor(widgets, text=text, width=140)
    reference = _show_reference_text_edit(
        widgets,
        text=text,
        width=box.viewport().width(),
        font=box.font(),
    )
    visual_lines = _reference_visual_lines(reference, text=text, app=app)
    last_line = visual_lines[-1]
    starting_position = last_line[max(0, len(last_line) // 2)]

    _set_cursor_position(box, starting_position)
    process_events(app)

    QTest.keyClick(box, Qt.Key.Key_Down)
    process_events(app)

    assert box.textCursor().position() == last_line[-1]


def test_projection_selection_shift_up_on_first_visual_line_extends_to_first_column(
    widgets: list[QWidget],
) -> None:
    """Shift+Up on the first visual line should preserve the anchor and select to column 0."""

    app = ensure_qapp()
    text = "alpha beta gamma delta epsilon zeta eta theta iota"
    box = show_prompt_editor(widgets, text=text, width=140)
    reference = _show_reference_text_edit(
        widgets,
        text=text,
        width=box.viewport().width(),
        font=box.font(),
    )
    visual_lines = _reference_visual_lines(reference, text=text, app=app)
    first_line = visual_lines[0]
    starting_position = first_line[min(len(first_line) - 1, 4)]

    _set_cursor_position(box, starting_position)
    process_events(app)

    QTest.keyClick(box, Qt.Key.Key_Up, Qt.KeyboardModifier.ShiftModifier)
    process_events(app)

    assert box.textCursor().position() == first_line[0]
    assert box.textCursor().selectionStart() == first_line[0]
    assert box.textCursor().selectionEnd() == starting_position


def test_projection_selection_shift_down_on_last_visual_line_extends_to_line_end(
    widgets: list[QWidget],
) -> None:
    """Shift+Down on the last visual line should preserve the anchor and select to line end."""

    app = ensure_qapp()
    text = "alpha beta gamma delta epsilon zeta eta theta iota"
    box = show_prompt_editor(widgets, text=text, width=140)
    reference = _show_reference_text_edit(
        widgets,
        text=text,
        width=box.viewport().width(),
        font=box.font(),
    )
    visual_lines = _reference_visual_lines(reference, text=text, app=app)
    last_line = visual_lines[-1]
    starting_position = last_line[max(0, len(last_line) // 2)]

    _set_cursor_position(box, starting_position)
    process_events(app)

    QTest.keyClick(box, Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier)
    process_events(app)

    assert box.textCursor().position() == last_line[-1]
    assert box.textCursor().selectionStart() == starting_position
    assert box.textCursor().selectionEnd() == last_line[-1]


def test_projection_selection_vertical_navigation_keeps_collapsed_emphasis_stable(
    widgets: list[QWidget],
) -> None:
    """Vertical movement should not expand or mutate a collapsed emphasis token."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="alpha\n(cat:1.05)\nomega",
        width=240,
    )
    token = _first_emphasis_token(box)
    assert token.content_start is not None

    _set_cursor_position(box, token.content_start + 1)
    process_events(app)

    QTest.keyClick(box, Qt.Key.Key_Down)
    QTest.keyClick(box, Qt.Key.Key_Up)
    process_events(app)

    assert box.toPlainText() == "alpha\n(cat:1.05)\nomega"
    assert _first_emphasis_token(box).display_text == "cat"
    assert box.textCursor().position() == token.content_start + 1


def test_projection_selection_vertical_navigation_keeps_collapsed_wildcard_stable(
    widgets: list[QWidget],
) -> None:
    """Vertical movement should keep wildcard navigation source-backed and unchanged."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="alpha\n{animal}\nomega",
        width=240,
        wildcard_gateway=StaticPromptWildcardCatalogGateway(
            {
                ("animal", "simple", None): PromptWildcardResolution(
                    identifier="animal",
                    wildcard_form="simple",
                    exists=True,
                ),
            }
        ),
    )
    token = _first_wildcard_token(box)

    _set_cursor_position(box, token.source_start)
    process_events(app)

    QTest.keyClick(box, Qt.Key.Key_Down)
    QTest.keyClick(box, Qt.Key.Key_Up)
    process_events(app)

    assert box.toPlainText() == "alpha\n{animal}\nomega"
    assert _first_wildcard_token(box).display_text == "animal"
    assert box.textCursor().position() == token.source_start


def test_projection_surface_set_active_span_does_not_rebuild_projection_geometry(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Caret-driven active-span changes should not rebuild the projection snapshot."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="alpha, (cat:1.05), omega",
        width=240,
    )
    surface = surface_for(box)
    _set_cursor_position(box, 0)
    process_events(app)

    rebuild_calls: list[str] = []
    monkeypatch.setattr(
        surface,
        "_rebuild_projection",
        lambda: rebuild_calls.append("rebuild"),
    )

    surface.set_active_span(
        PromptSyntaxSpanView(kind="emphasis", start=7, end=17, depth=0),
        cursor_position=10,
    )

    assert rebuild_calls == []

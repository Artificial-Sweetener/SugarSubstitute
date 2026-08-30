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

"""Provide native-reference and projection-selection helpers."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QFont, QTextCursor, QTextOption
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QTextEdit, QWidget

from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
    PromptProjectionTokenKind,
)
from tests.support.prompt_editor.projection_engine_support import (
    process_events,
    set_prompt_cursor_position as _set_cursor_position,
    surface_for,
)

__all__ = [
    "_assert_pointer_selection_matches_reference",
    "_drag_select",
    "_drive_vertical_key_on_both",
    "_first_emphasis_token",
    "_first_lora_token",
    "_first_wildcard_token",
    "_line_interior_position",
    "_point_for_source_position",
    "_projection_visual_lines",
    "_reference_click_point_for_position",
    "_reference_visual_lines",
    "_selection_bounds",
    "_set_cursor_position",
    "_set_reference_cursor_position",
    "_set_selection_range",
    "_show_reference_text_edit",
    "_stable_projection_click_point_for_position",
    "_stable_reference_click_point_for_position",
]


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


def _assert_pointer_selection_matches_reference(
    box: PromptEditor,
    reference: QTextEdit,
) -> None:
    """Allow one caret boundary of subpixel ambiguity for pointer selection."""

    actual = _selection_bounds(box)
    expected = _selection_bounds(reference)
    assert all(
        abs(actual_position - expected_position) <= 1
        for actual_position, expected_position in zip(actual, expected, strict=True)
    )


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

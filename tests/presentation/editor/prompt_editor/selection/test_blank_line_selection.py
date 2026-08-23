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

"""Verify blank-line and newline selection geometry."""

from __future__ import annotations


from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPalette, QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)
from tests.presentation.editor.prompt_editor.selection.support import (
    _assert_pointer_selection_matches_reference,
    _drag_select,
    _reference_click_point_for_position,
    _reference_visual_lines,
    _show_reference_text_edit,
    _stable_projection_click_point_for_position,
)


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

    _assert_pointer_selection_matches_reference(box, reference)


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
        for line in surface._layout.frame.output.snapshot.lines
        if not line.fragments  # noqa: SLF001
    )
    selection_rects = surface._layout.frame.geometry.selection.selection_rects(
        surface._selection()
    )  # noqa: SLF001
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
    selection_rects = surface._layout.frame.geometry.selection.selection_rects(
        surface._selection()
    )  # noqa: SLF001
    painted_line_tops = {
        round(rect.top(), 1) for rect in selection_rects if rect.width() >= 8.0
    }

    assert box.textCursor().selectedText() == "\n"
    assert len(painted_line_tops) == 1
    assert painted_line_tops == {  # noqa: SLF001
        round(surface._layout.frame.output.snapshot.lines[0].top, 1)
    }


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
    selection_rects = surface._layout.frame.geometry.selection.selection_rects(
        surface._selection()
    )  # noqa: SLF001
    empty_line = next(
        line
        for line in surface._layout.frame.output.snapshot.lines
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
        for line in surface._layout.frame.output.snapshot.lines
        if not line.fragments  # noqa: SLF001
    )
    selection_rects = surface._layout.frame.geometry.selection.selection_rects(
        surface._selection()
    )  # noqa: SLF001
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

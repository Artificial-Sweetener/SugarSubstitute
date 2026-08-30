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

"""Verify vertical selection behavior at document and token boundaries."""

from __future__ import annotations


from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from substitute.application.ports import PromptWildcardResolution
from tests.support.prompt_editor.projection_engine_support import (
    StaticPromptWildcardCatalogGateway,
    ensure_qapp,
    process_events,
    show_prompt_editor,
)
from tests.presentation.editor.prompt_editor.selection.support import (
    _first_emphasis_token,
    _first_wildcard_token,
    _reference_visual_lines,
    _set_cursor_position,
    _show_reference_text_edit,
)


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

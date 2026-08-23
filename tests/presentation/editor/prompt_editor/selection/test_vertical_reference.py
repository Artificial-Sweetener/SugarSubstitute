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

"""Verify vertical selection navigation against native Qt behavior."""

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
    _drive_vertical_key_on_both,
    _first_wildcard_token,
    _reference_visual_lines,
    _set_cursor_position,
    _set_reference_cursor_position,
    _show_reference_text_edit,
)


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

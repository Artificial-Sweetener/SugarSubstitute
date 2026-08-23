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

"""Verify token-aware selection navigation boundaries."""

from __future__ import annotations


from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
    process_events,
    show_prompt_editor,
)
from tests.presentation.editor.prompt_editor.selection.support import (
    _first_emphasis_token,
    _line_interior_position,
    _reference_visual_lines,
    _selection_bounds,
    _set_cursor_position,
    _set_reference_cursor_position,
    _set_selection_range,
    _show_reference_text_edit,
)


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

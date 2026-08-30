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

"""Verify wrapped plain-text drags against native Qt behavior."""

from __future__ import annotations


from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QWidget

from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
    process_events,
    show_prompt_editor,
)
from tests.presentation.editor.prompt_editor.selection.support import (
    _assert_pointer_selection_matches_reference,
    _drag_select,
    _line_interior_position,
    _reference_visual_lines,
    _show_reference_text_edit,
    _stable_projection_click_point_for_position,
    _stable_reference_click_point_for_position,
)


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

    _assert_pointer_selection_matches_reference(box, reference)


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

    _assert_pointer_selection_matches_reference(box, reference)


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

    _assert_pointer_selection_matches_reference(box, reference)


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

    _assert_pointer_selection_matches_reference(box, reference)


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

    _assert_pointer_selection_matches_reference(box, reference)


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
    assert len(visual_lines) >= 4
    start_position = visual_lines[0][0]
    target_line = visual_lines[-1]
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

    _assert_pointer_selection_matches_reference(box, reference)

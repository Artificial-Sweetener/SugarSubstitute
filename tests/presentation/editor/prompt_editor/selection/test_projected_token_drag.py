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

"""Verify pointer drags across projected token rows."""

from __future__ import annotations


from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QWidget

from substitute.application.ports import PromptWildcardResolution
from tests.support.prompt_editor.projection_engine_support import (
    StaticPromptWildcardCatalogGateway,
    ensure_qapp,
    process_events,
    show_prompt_editor,
)
from tests.presentation.editor.prompt_editor.selection.support import (
    _drag_select,
    _line_interior_position,
    _projection_visual_lines,
    _stable_projection_click_point_for_position,
)


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

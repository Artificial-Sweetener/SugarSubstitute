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

"""Verify live and scrolled pointer-drag feedback."""

from __future__ import annotations


from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPalette
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
    _line_interior_position,
    _reference_visual_lines,
    _show_reference_text_edit,
    _stable_projection_click_point_for_position,
    _stable_reference_click_point_for_position,
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
    selection_rects = surface._layout.frame.geometry.selection.selection_rects(
        surface._selection()
    )
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


def test_projection_selection_drag_to_last_character_after_scroll_matches_qt_reference(
    widgets: list[QWidget],
) -> None:
    """Dragging across the scrolled final paragraph should match Qt selection."""

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
    box.verticalScrollBar().setValue(box.verticalScrollBar().maximum())
    reference.verticalScrollBar().setValue(reference.verticalScrollBar().maximum())
    process_events(app)
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
    reference_drag_end = _stable_reference_click_point_for_position(
        reference,
        final_position,
        app=app,
    )
    box_drag_end = _stable_projection_click_point_for_position(
        box,
        final_position,
        app=app,
    )

    QTest.mousePress(
        box.viewport(),
        Qt.MouseButton.LeftButton,
        pos=box_anchor,
    )
    QTest.mouseMove(box.viewport(), box_drag_end, 10)
    process_events(app)

    QTest.mousePress(
        reference.viewport(),
        Qt.MouseButton.LeftButton,
        pos=reference_anchor,
    )
    QTest.mouseMove(reference.viewport(), reference_drag_end, 10)
    process_events(app)

    _assert_pointer_selection_matches_reference(box, reference)

    QTest.mouseRelease(
        box.viewport(),
        Qt.MouseButton.LeftButton,
        pos=box_drag_end,
        delay=10,
    )
    QTest.mouseRelease(
        reference.viewport(),
        Qt.MouseButton.LeftButton,
        pos=reference_drag_end,
        delay=10,
    )
    process_events(app)

    _assert_pointer_selection_matches_reference(box, reference)

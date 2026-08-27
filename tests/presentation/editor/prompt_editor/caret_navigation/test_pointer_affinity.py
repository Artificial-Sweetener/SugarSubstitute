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

"""Verify pointer placement preserves visual-row affinity."""

from __future__ import annotations


import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from tests.presentation.editor.prompt_editor.caret_navigation.support import (
    _projection_lines,
)
from tests.support.prompt_editor.projection_engine_support import (
    show_prompt_editor,
    surface_for,
    wait_for_caret_geometry,
)
from tests.support.prompt_editor.projection_surface_support import (
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
)


def test_projection_surface_click_empty_space_keeps_short_line_affinity(
    widgets: list[QWidget],
) -> None:
    """Clicking past short line text should place the caret at that line's end."""

    box = show_prompt_editor(
        widgets,
        text="short row\na very long row with a lot of text on it",
        width=360,
    )
    surface = surface_for(box)
    first_line, second_line = _projection_lines(surface)[:2]
    click_point = QPoint(
        surface.viewport().width() - 12,
        int(first_line.top + (first_line.height / 2.0)),
    )

    QTest.mouseClick(
        box.viewport(),
        Qt.MouseButton.LeftButton,
        pos=click_point,
    )
    expected_rect = first_line.caret_stops[-1].rect
    wait_for_caret_geometry(
        box,
        surface,
        position=first_line.source_content_end,
        expected_x=expected_rect.x(),
        expected_y=expected_rect.y(),
    )

    caret_rect = box.cursorRect()
    assert surface.cursor_position == first_line.source_content_end
    assert caret_rect.x() == pytest.approx(expected_rect.x(), abs=1.0)
    assert caret_rect.y() == pytest.approx(expected_rect.y(), abs=1.0)
    assert caret_rect.y() < second_line.top


def test_projection_surface_click_wrapped_trailing_edge_keeps_visual_row(
    widgets: list[QWidget],
) -> None:
    """Clicking a wrapped row's right edge should not jump to next-row leading x."""

    box = show_prompt_editor(
        widgets,
        text="alpha beta gamma delta epsilon zeta eta theta iota kappa lambda",
        width=180,
    )
    surface = surface_for(box)
    first_line, second_line = _projection_lines(surface)[:2]
    click_point = QPoint(
        surface.viewport().width() - 8,
        int(first_line.top + (first_line.height / 2.0)),
    )

    QTest.mouseClick(
        box.viewport(),
        Qt.MouseButton.LeftButton,
        pos=click_point,
    )
    expected_rect = first_line.caret_stops[-1].rect
    wait_for_caret_geometry(
        box,
        surface,
        position=first_line.source_content_end,
        expected_x=expected_rect.x(),
        expected_y=expected_rect.y(),
    )

    caret_rect = box.cursorRect()
    assert surface.cursor_position == first_line.source_content_end
    assert caret_rect.x() == pytest.approx(expected_rect.x(), abs=1.0)
    assert caret_rect.y() == pytest.approx(expected_rect.y(), abs=1.0)
    assert caret_rect.y() < second_line.top


def test_projection_surface_click_wrapped_leading_edge_uses_clicked_row(
    widgets: list[QWidget],
) -> None:
    """Clicking the next wrapped row's left edge should keep that row affinity."""

    box = show_prompt_editor(
        widgets,
        text="alpha beta gamma delta epsilon zeta eta theta iota kappa lambda",
        width=180,
    )
    surface = surface_for(box)
    _, second_line = _projection_lines(surface)[:2]
    expected_rect = second_line.caret_stops[0].rect
    click_point = QPoint(
        int(expected_rect.x() + 1.0),
        int(second_line.top + (second_line.height / 2.0)),
    )

    QTest.mouseClick(
        box.viewport(),
        Qt.MouseButton.LeftButton,
        pos=click_point,
    )
    wait_for_caret_geometry(
        box,
        surface,
        position=second_line.source_content_start,
        expected_x=expected_rect.x(),
        expected_y=expected_rect.y(),
    )

    caret_rect = box.cursorRect()
    assert surface.cursor_position == second_line.source_content_start
    assert caret_rect.x() == pytest.approx(expected_rect.x(), abs=1.0)
    assert caret_rect.y() == pytest.approx(expected_rect.y(), abs=1.0)


def test_projection_surface_inside_text_click_preserves_boundary_precision(
    widgets: list[QWidget],
) -> None:
    """Clicking inside text should still use the nearest glyph boundary."""

    box = show_prompt_editor(
        widgets,
        text="alpha beta",
        width=240,
    )
    surface = surface_for(box)
    expected_position = 3
    expected_rect = surface._layout.frame.geometry.caret.cursor_rect(  # noqa: SLF001
        surface.projection_document().caret_map.state_for_source_position(
            expected_position
        ),
        scroll_offset=0.0,
    )

    QTest.mouseClick(
        box.viewport(),
        Qt.MouseButton.LeftButton,
        pos=expected_rect.center().toPoint(),
    )
    wait_for_caret_geometry(
        box,
        surface,
        position=expected_position,
        expected_x=expected_rect.x(),
        expected_y=expected_rect.y(),
    )

    caret_rect = box.cursorRect()
    assert surface.cursor_position == expected_position
    assert caret_rect.x() == pytest.approx(expected_rect.x(), abs=1.0)
    assert caret_rect.y() == pytest.approx(expected_rect.y(), abs=1.0)

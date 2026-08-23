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

"""Verify blank-line caret placement and editing."""

from __future__ import annotations


import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
    process_events,
    show_prompt_editor,
)
from tests.support.prompt_editor.projection_surface_support import (
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
)
from tests.presentation.editor.prompt_editor.caret_navigation.support import (
    _CaretPlacementHarness,
    _projection_lines,
)


def test_projection_surface_caret_placement_harness_backspace_after_erasing_second_line(
    widgets: list[QWidget],
) -> None:
    """Backspace after erasing second-line text should keep blank-line navigation valid."""

    app = ensure_qapp()
    erased_text = "fajsklfajfkla"
    box = show_prompt_editor(
        widgets,
        text=f"\n{erased_text}",
        width=360,
    )
    harness = _CaretPlacementHarness(box, app=app, inset=32.0)
    surface = harness.surface
    harness.set_cursor(len(box.toPlainText()))

    for _character in erased_text:
        harness.key(Qt.Key.Key_Backspace)

    assert box.toPlainText() == "\n"
    assert surface.cursor_position == 1
    harness.assert_caret_at_line_start(1, "after erasing second-line text")

    harness.key(Qt.Key.Key_Backspace)

    assert box.toPlainText() == ""
    assert surface.cursor_position == 0
    harness.assert_caret_at_line_start(0, "after deleting leading line break")

    harness.key(Qt.Key.Key_Down)
    assert surface.cursor_position == 0
    harness.assert_caret_at_line_start(0, "down after deleting leading line break")


def test_projection_surface_caret_placement_harness_backspace_after_incremental_second_line(
    widgets: list[QWidget],
) -> None:
    """Backspace after incrementally-created second-line text should not strand caret."""

    app = ensure_qapp()
    erased_text = "fajsklfajfkla"
    box = show_prompt_editor(
        widgets,
        text="",
        width=360,
    )
    harness = _CaretPlacementHarness(box, app=app, inset=32.0)
    surface = harness.surface

    harness.key(Qt.Key.Key_Return)
    harness.type_text(erased_text)

    assert box.toPlainText() == f"\n{erased_text}"
    harness.assert_caret_valid("after creating second-line text")

    for _character in erased_text:
        harness.key(Qt.Key.Key_Backspace)

    assert box.toPlainText() == "\n"
    assert surface.cursor_position == 1
    harness.assert_caret_at_line_start(1, "after erasing incremental second-line text")

    harness.key(Qt.Key.Key_Backspace)

    assert box.toPlainText() == ""
    assert surface.cursor_position == 0
    harness.assert_caret_at_line_start(0, "after deleting incremental line break")

    harness.key(Qt.Key.Key_Down)
    assert surface.cursor_position == 0
    harness.assert_caret_at_line_start(0, "down after deleting incremental line break")


def test_projection_surface_caret_placement_harness_backspace_after_selection_erases_second_line(
    widgets: list[QWidget],
) -> None:
    """Selection-erasing second-line text should leave newline Backspace navigable."""

    app = ensure_qapp()
    erased_text = "fajsklfajfkla"
    box = show_prompt_editor(
        widgets,
        text=f"\n{erased_text}",
        width=360,
    )
    harness = _CaretPlacementHarness(box, app=app, inset=32.0)
    surface = harness.surface
    surface.set_cursor_positions(
        cursor_position=len(box.toPlainText()),
        anchor_position=1,
    )
    process_events(app)

    QTest.keyClick(box, Qt.Key.Key_Backspace)
    harness.assert_caret_valid("after selection erases second-line text")

    assert box.toPlainText() == "\n"
    assert surface.cursor_position == 1
    harness.assert_caret_at_line_start(1, "after selection-erasing second-line text")

    QTest.keyClick(box, Qt.Key.Key_Backspace)
    harness.assert_caret_valid("after Backspace deletes selection-erased line break")

    assert box.toPlainText() == ""
    assert surface.cursor_position == 0
    harness.assert_caret_at_line_start(
        0,
        "after deleting selection-erased line break",
    )

    QTest.keyClick(box, Qt.Key.Key_Down)
    assert surface.cursor_position == 0
    harness.assert_caret_at_line_start(
        0,
        "down after deleting selection-erased line break",
    )


def test_projection_surface_caret_placement_harness_backspace_after_erasing_indented_second_line(
    widgets: list[QWidget],
) -> None:
    """Backspace after erasing an indented second line should stay on that line."""

    app = ensure_qapp()
    erased_text = "fajsklfajfkla"
    box = show_prompt_editor(
        widgets,
        text=f"\n {erased_text}",
        width=360,
    )
    harness = _CaretPlacementHarness(box, app=app, inset=32.0)
    surface = harness.surface
    harness.set_cursor(len(box.toPlainText()))

    for _character in erased_text:
        harness.key(Qt.Key.Key_Backspace)

    assert box.toPlainText() == "\n "
    assert surface.cursor_position == 2
    caret_after_word_delete = harness.assert_caret_valid(
        "after erasing indented second-line text",
    )
    second_line = _projection_lines(surface)[1]
    assert caret_after_word_delete.top() == pytest.approx(second_line.top, abs=1.0)
    assert caret_after_word_delete.left() > harness.content_left

    harness.key(Qt.Key.Key_Backspace)

    assert box.toPlainText() == "\n"
    assert surface.cursor_position == 1
    harness.assert_caret_at_line_start(
        1,
        "after deleting second-line indentation",
    )

    harness.key(Qt.Key.Key_Down)
    assert surface.cursor_position == 1
    harness.assert_caret_at_line_start(
        1,
        "down after deleting second-line indentation",
    )


def test_projection_surface_caret_placement_harness_backspace_burst_after_indented_second_line(
    widgets: list[QWidget],
) -> None:
    """Rapid erase then Backspace should not leave caret above the remaining blank line."""

    app = ensure_qapp()
    erased_text = "fajsklfajfkla"
    box = show_prompt_editor(
        widgets,
        text=f"\n {erased_text}",
        width=360,
    )
    harness = _CaretPlacementHarness(box, app=app, inset=32.0)
    surface = harness.surface
    surface.set_cursor_positions(
        cursor_position=len(box.toPlainText()),
        anchor_position=len(box.toPlainText()),
    )
    process_events(app)

    for _character in erased_text:
        QTest.keyClick(box, Qt.Key.Key_Backspace)
    QTest.keyClick(box, Qt.Key.Key_Backspace)
    process_events(app)

    assert box.toPlainText() == "\n"
    assert surface.cursor_position == 1
    harness.assert_caret_at_line_start(
        1,
        "after rapid deleting second-line indentation",
    )

    QTest.keyClick(box, Qt.Key.Key_Down)
    process_events(app)

    assert surface.cursor_position == 1
    harness.assert_caret_at_line_start(
        1,
        "down after rapid deleting second-line indentation",
    )


def test_projection_surface_caret_placement_harness_down_from_first_blank_to_indented_blank(
    widgets: list[QWidget],
) -> None:
    """Down from the first blank line should reach a second whitespace-only line."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="\n ",
        width=360,
    )
    harness = _CaretPlacementHarness(box, app=app, inset=32.0)
    surface = harness.surface
    harness.set_cursor(0)

    harness.key(Qt.Key.Key_Down)

    assert surface.cursor_position in {1, 2}
    second_line = _projection_lines(surface)[1]
    caret_rect = harness.assert_caret_valid(
        "down from first blank to indented blank",
    )
    assert caret_rect.top() == pytest.approx(second_line.top, abs=1.0)

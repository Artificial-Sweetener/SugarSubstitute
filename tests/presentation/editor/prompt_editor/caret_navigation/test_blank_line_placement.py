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
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)
from tests.support.prompt_editor.projection_surface_support import (
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
)
from tests.presentation.editor.prompt_editor.caret_navigation.support import (
    _CaretPlacementHarness,
    _projection_lines,
)


def test_projection_surface_incremental_blank_line_click_uses_content_start(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Clicking an incrementally-created blank line should land at content start."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="alpha\nbeta",
        width=360,
    )
    surface = surface_for(box)
    surface.set_source_line_content_left_inset(24.0)
    process_events(app)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    cursor_position = len("alpha\n")
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0

    QTest.keyClick(box, Qt.Key.Key_Return)
    process_events(app)

    assert box.toPlainText() == "alpha\n\nbeta"
    assert rebuild_count == 0
    blank_line = _projection_lines(surface)[1]
    content_left = (  # noqa: SLF001
        surface._layout.frame.output.configuration.document_margin + 24.0
    )
    QTest.mouseClick(
        box.viewport(),
        Qt.MouseButton.LeftButton,
        pos=QPoint(2, int(blank_line.top + (blank_line.height / 2.0))),
    )
    process_events(app)

    caret_rect = box.cursorRect()
    assert surface.cursor_position == len("alpha\n")
    assert caret_rect.x() == pytest.approx(content_left, abs=1.0)
    assert caret_rect.y() == pytest.approx(blank_line.top, abs=1.0)


def test_projection_surface_vertical_navigation_reaches_incremental_blank_line(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Up and Down should traverse an incrementally-created blank visual line."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="alpha\nbeta",
        width=360,
    )
    surface = surface_for(box)
    surface.set_source_line_content_left_inset(24.0)
    process_events(app)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    cursor_position = len("alpha\n")
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0

    QTest.keyClick(box, Qt.Key.Key_Return)
    process_events(app)

    first_line, blank_line, third_line = _projection_lines(surface)[:3]
    surface.set_cursor_positions(cursor_position=0, anchor_position=0)
    process_events(app)

    QTest.keyClick(box, Qt.Key.Key_Down)
    process_events(app)
    assert surface.cursor_position == blank_line.source_content_start
    assert box.cursorRect().y() == pytest.approx(blank_line.top, abs=1.0)

    QTest.keyClick(box, Qt.Key.Key_Down)
    process_events(app)
    assert surface.cursor_position == third_line.source_content_start
    assert box.cursorRect().y() == pytest.approx(third_line.top, abs=1.0)

    QTest.keyClick(box, Qt.Key.Key_Up)
    process_events(app)
    assert surface.cursor_position == blank_line.source_content_start
    assert box.cursorRect().y() == pytest.approx(blank_line.top, abs=1.0)

    QTest.keyClick(box, Qt.Key.Key_Up)
    process_events(app)
    assert surface.cursor_position == first_line.source_content_start
    assert box.cursorRect().y() == pytest.approx(first_line.top, abs=1.0)
    assert rebuild_count == 0


def test_projection_surface_caret_placement_harness_keeps_blank_lines_out_of_margin(
    widgets: list[QWidget],
) -> None:
    """Caret placement should stay at content-left across blank-line edits."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="alpha\nbeta\ngamma",
        width=360,
    )
    harness = _CaretPlacementHarness(box, app=app, inset=32.0)
    surface = harness.surface

    harness.set_cursor(len("alpha\n"))
    harness.key(Qt.Key.Key_Return)
    assert box.toPlainText() == "alpha\n\nbeta\ngamma"

    harness.click_visual_line_start(1)
    assert surface.cursor_position == len("alpha\n")
    harness.assert_caret_at_line_start(1, "blank-line click")

    harness.key(Qt.Key.Key_Down)
    assert surface.cursor_position == len("alpha\n\n")
    harness.assert_caret_at_line_start(2, "down from blank line")

    harness.key(Qt.Key.Key_Up)
    assert surface.cursor_position == len("alpha\n")
    harness.assert_caret_at_line_start(1, "up to blank line")

    harness.set_cursor(len("alpha\n\n"))
    harness.key(Qt.Key.Key_Backspace)
    assert box.toPlainText() == "alpha\nbeta\ngamma"
    harness.assert_caret_at_line_start(1, "backspace removed blank line")

    harness.key(Qt.Key.Key_Backspace)
    assert box.toPlainText() == "alphabeta\ngamma"
    harness.assert_caret_valid("backspace removed hard line break")


def test_projection_surface_caret_placement_harness_splits_empty_line_at_content_start(
    widgets: list[QWidget],
) -> None:
    """Enter before an empty-line newline should keep both blank carets aligned."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="alpha\n\nbeta",
        width=360,
    )
    harness = _CaretPlacementHarness(box, app=app, inset=32.0)

    harness.set_cursor(len("alpha\n"))
    harness.key(Qt.Key.Key_Return)

    assert box.toPlainText() == "alpha\n\n\nbeta"
    harness.assert_caret_at_line_start(2, "empty-line split inserted blank line")
    for line_index in (1, 2):
        line = _projection_lines(harness.surface)[line_index]
        assert line.caret_stops
        assert line.caret_stops[0].rect.left() == pytest.approx(
            harness.content_left,
            abs=1.0,
        )

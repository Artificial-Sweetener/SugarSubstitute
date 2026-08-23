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

"""Verify keyboard navigation across wrapped projection rows."""

from __future__ import annotations


import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)
from tests.support.prompt_editor.projection_surface_support import (
    delay_projection_update_scheduler as _delay_projection_update_scheduler,
    flush_semantic_refresh as _flush_semantic_refresh,
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
)
from tests.presentation.editor.prompt_editor.caret_navigation.support import (
    _projection_lines,
)


def test_projection_surface_right_arrow_steps_through_wrapped_row_boundary(
    widgets: list[QWidget],
) -> None:
    """Right arrow should visit both visual stops at a soft-wrap boundary."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="alpha beta gamma delta epsilon zeta eta theta iota kappa lambda",
        width=180,
    )
    surface = surface_for(box)
    first_line, second_line = _projection_lines(surface)[:2]
    start_position = first_line.source_content_end - 1
    surface.set_cursor_positions(
        cursor_position=start_position,
        anchor_position=start_position,
    )
    process_events(app)

    QTest.keyClick(box, Qt.Key.Key_Right)
    process_events(app)

    first_edge_rect = first_line.caret_stops[-1].rect
    caret_rect = box.cursorRect()
    assert surface.cursor_position == first_line.source_content_end
    assert caret_rect.x() == pytest.approx(first_edge_rect.x(), abs=1.0)
    assert caret_rect.y() == pytest.approx(first_edge_rect.y(), abs=1.0)

    QTest.keyClick(box, Qt.Key.Key_Right)
    process_events(app)

    second_edge_rect = second_line.caret_stops[0].rect
    caret_rect = box.cursorRect()
    assert surface.cursor_position == second_line.source_content_start
    assert caret_rect.x() == pytest.approx(second_edge_rect.x(), abs=1.0)
    assert caret_rect.y() == pytest.approx(second_edge_rect.y(), abs=1.0)

    QTest.keyClick(box, Qt.Key.Key_Right)
    process_events(app)

    assert surface.cursor_position == second_line.source_content_start + 1


def test_projection_surface_left_arrow_steps_through_wrapped_row_boundary(
    widgets: list[QWidget],
) -> None:
    """Left arrow should visit both visual stops at a soft-wrap boundary."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="alpha beta gamma delta epsilon zeta eta theta iota kappa lambda",
        width=180,
    )
    surface = surface_for(box)
    first_line, second_line = _projection_lines(surface)[:2]
    start_position = second_line.source_content_start + 1
    surface.set_cursor_positions(
        cursor_position=start_position,
        anchor_position=start_position,
    )
    process_events(app)

    QTest.keyClick(box, Qt.Key.Key_Left)
    process_events(app)

    second_edge_rect = second_line.caret_stops[0].rect
    caret_rect = box.cursorRect()
    assert surface.cursor_position == second_line.source_content_start
    assert caret_rect.x() == pytest.approx(second_edge_rect.x(), abs=1.0)
    assert caret_rect.y() == pytest.approx(second_edge_rect.y(), abs=1.0)

    QTest.keyClick(box, Qt.Key.Key_Left)
    process_events(app)

    first_edge_rect = first_line.caret_stops[-1].rect
    caret_rect = box.cursorRect()
    assert surface.cursor_position == first_line.source_content_end
    assert caret_rect.x() == pytest.approx(first_edge_rect.x(), abs=1.0)
    assert caret_rect.y() == pytest.approx(first_edge_rect.y(), abs=1.0)

    QTest.keyClick(box, Qt.Key.Key_Left)
    process_events(app)

    assert surface.cursor_position == first_line.source_content_end - 1


def test_projection_surface_arrow_navigation_flushes_pending_projection_update(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exact keyboard navigation should flush pending projection work first."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), ",
        width=240,
    )
    surface = surface_for(box)
    _delay_projection_update_scheduler(surface)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0

    QTest.keyClicks(box, "x")
    _flush_semantic_refresh(box)

    assert surface.has_pending_projection_update() is True
    assert rebuild_count == 0

    QTest.keyClick(box, Qt.Key.Key_Left)

    assert surface.has_pending_projection_update() is False
    assert rebuild_count == 0


def test_projection_surface_vertical_navigation_preserves_pending_stale_safe_update(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vertical arrows should not synchronously flush stale-safe typing projection."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), \nbeta",
        width=240,
    )
    surface = surface_for(box)
    _delay_projection_update_scheduler(surface)
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )

    QTest.keyClicks(box, "x")
    _flush_semantic_refresh(box)

    assert surface.has_pending_projection_update() is True
    flush_calls: list[str] = []

    def record_flush(*, reason: str) -> None:
        """Record an unexpected synchronous projection flush."""

        flush_calls.append(reason)

    monkeypatch.setattr(surface, "_flush_pending_projection_update", record_flush)

    QTest.keyClick(box, Qt.Key.Key_Up)

    assert flush_calls == []
    assert surface.has_pending_projection_update() is True

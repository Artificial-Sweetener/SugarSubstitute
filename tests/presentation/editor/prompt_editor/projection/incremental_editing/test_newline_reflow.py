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

"""Tests for prompt projection incremental editing surface behavior."""

from __future__ import annotations

from typing import Any, cast


import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretState,
)
from tests.support.prompt_editor.projection_engine_support import (
    show_prompt_editor,
    surface_for,
    wait_for_caret_geometry,
)
from tests.support.prompt_editor.projection_surface_support import (
    delay_projection_update_scheduler,
    flush_projection_update_scheduler,
    flush_semantic_refresh,
    install_lora_wildcard_prompt_state,
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
)
from tests.support.qt.semantic_wait import wait_for_qt_condition

from .support import (
    _projection_lines,
)


def test_projection_surface_backspace_newline_uses_incremental_layout(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deleting a middle hard line break should publish authoritative geometry."""

    box = show_prompt_editor(
        widgets,
        text="alpha\nbeta",
        width=360,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
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
    previous_line_count = cast(  # noqa: SLF001
        Any, surface
    )._layout.frame.output.snapshot.line_count()

    QTest.keyClick(box, Qt.Key.Key_Backspace)

    assert box.toPlainText() == "alphabeta"
    assert rebuild_count == 0
    assert (
        cast(Any, surface)._layout.frame.output.snapshot.line_count()  # noqa: SLF001
        == previous_line_count - 1
    )
    assert cast(Any, surface)._caret_visibility_prompt_state_revision is None
    assert surface.has_stale_projection_geometry() is False
    flush_projection_update_scheduler(surface)


def test_projection_surface_middle_enter_uses_incremental_layout(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Middle Enter should publish authoritative line-break geometry."""

    box = show_prompt_editor(
        widgets,
        text="alphabeta",
        width=360,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    cursor_position = len("alpha")
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0
    previous_line_count = cast(  # noqa: SLF001
        Any, surface
    )._layout.frame.output.snapshot.line_count()

    QTest.keyClick(box, Qt.Key.Key_Return)

    assert box.toPlainText() == "alpha\nbeta"
    assert rebuild_count == 0
    assert (
        cast(Any, surface)._layout.frame.output.snapshot.line_count()  # noqa: SLF001
        == previous_line_count + 1
    )
    assert surface.has_stale_projection_geometry() is False
    flush_projection_update_scheduler(surface)


def test_projection_surface_middle_enter_after_lora_keeps_caret_on_new_line(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Enter after projected tokens should keep typed text on the inserted line."""

    text = "<lora:midna:1>\nalphabeta"
    box = show_prompt_editor(
        widgets,
        text=text,
        width=360,
        syntaxes=("emphasis", "wildcard", "lora"),
    )
    surface = surface_for(box)
    install_lora_wildcard_prompt_state(surface, text)
    delay_projection_update_scheduler(surface)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    cursor_position = len("<lora:midna:1>\nalpha")
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0

    QTest.keyClick(box, Qt.Key.Key_Return)
    QTest.keyClicks(box, "X")

    assert box.toPlainText() == "<lora:midna:1>\nalpha\nXbeta"
    assert rebuild_count == 0
    assert surface.has_stale_projection_geometry() is False
    flush_projection_update_scheduler(surface)


def test_projection_surface_middle_enter_with_inset_keeps_ordered_line_carets(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Incremental Enter should keep line-local caret stops in source order."""

    box = show_prompt_editor(
        widgets,
        text="alphabeta",
        width=360,
    )
    surface = surface_for(box)
    surface.set_source_line_content_left_inset(24.0)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    cursor_position = len("alpha")
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0

    QTest.keyClick(box, Qt.Key.Key_Return)
    wait_for_qt_condition(
        lambda: (
            box.toPlainText() == "alpha\nbeta"
            and len(_projection_lines(surface)) >= 2
            and not surface.has_pending_projection_update()
            and not surface.has_stale_projection_geometry()
        ),
        description="incremental newline projection geometry",
        state=lambda: {
            "text": box.toPlainText(),
            "line_count": len(_projection_lines(surface)),
            "pending_projection": surface.has_pending_projection_update(),
            "stale_geometry": surface.has_stale_projection_geometry(),
        },
    )

    first_line, second_line = _projection_lines(surface)[:2]
    first_line_positions = tuple(
        caret_stop.projection_position for caret_stop in first_line.caret_stops
    )
    content_left = (  # noqa: SLF001
        surface._layout.frame.output.configuration.document_margin + 24.0
    )
    assert box.toPlainText() == "alpha\nbeta"
    assert rebuild_count == 0
    assert first_line_positions == tuple(sorted(first_line_positions))
    assert first_line.caret_stops[-1].projection_position == len("alpha")
    assert second_line.caret_stops[0].projection_position == len("alpha\n")
    wait_for_caret_geometry(
        box,
        surface,
        position=len("alpha\n"),
        expected_x=content_left,
        expected_y=second_line.top,
    )

    QTest.keyClick(box, Qt.Key.Key_Left)
    wait_for_caret_geometry(
        box,
        surface,
        position=len("alpha"),
        expected_x=first_line.caret_stops[-1].rect.x(),
        expected_y=first_line.top,
    )
    caret_rect = box.cursorRect()
    assert surface.cursor_position == len("alpha")
    assert caret_rect.x() == pytest.approx(first_line.caret_stops[-1].rect.x(), abs=1.0)
    assert caret_rect.y() == pytest.approx(
        first_line.top - surface.verticalScrollBar().value(),
        abs=1.0,
    )

    QTest.keyClick(box, Qt.Key.Key_Right)
    wait_for_caret_geometry(
        box,
        surface,
        position=len("alpha\n"),
        expected_x=content_left,
        expected_y=second_line.top,
    )
    caret_rect = box.cursorRect()
    assert surface.cursor_position == len("alpha\n")
    assert caret_rect.x() == pytest.approx(content_left, abs=1.0)
    assert caret_rect.y() == pytest.approx(
        second_line.top - surface.verticalScrollBar().value(),
        abs=1.0,
    )


def test_projection_surface_backspace_newline_after_lora_keeps_geometry_aligned(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deleting a newline after projected tokens should keep source/projection aligned."""

    text = "<lora:midna:1.00>\nalpha\nbeta"
    box = show_prompt_editor(
        widgets,
        text=text,
        width=360,
        syntaxes=("emphasis", "wildcard", "lora"),
    )
    surface = surface_for(box)
    install_lora_wildcard_prompt_state(surface, text)
    installed_text = box.toPlainText()
    delay_projection_update_scheduler(surface)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    cursor_position = installed_text.index("\n", installed_text.index("alpha")) + 1
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0

    QTest.keyClick(box, Qt.Key.Key_Backspace)
    QTest.keyClicks(box, "X")

    lines = box.toPlainText().splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("<lora:midna:")
    assert lines[1] == "alphaXbeta"
    assert rebuild_count == 0
    assert surface.has_stale_projection_geometry() is False
    flush_projection_update_scheduler(surface)


def test_projection_surface_trailing_enter_uses_incremental_newline_layout(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trailing Enter should append one layout row without full projection rebuild."""

    box = show_prompt_editor(
        widgets,
        text="alpha",
        width=360,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
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
    previous_line_count = cast(  # noqa: SLF001
        Any, surface
    )._layout.frame.output.snapshot.line_count()

    QTest.keyClick(box, Qt.Key.Key_Return)

    assert box.toPlainText() == "alpha\n"
    assert rebuild_count == 0
    assert (
        cast(Any, surface)._layout.frame.output.snapshot.line_count()  # noqa: SLF001
        == previous_line_count + 1
    )
    assert surface.has_stale_projection_geometry() is False


def test_projection_surface_trailing_newline_backspace_uses_incremental_layout(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trailing newline backspace should drop one layout row without full rebuild."""

    box = show_prompt_editor(
        widgets,
        text="alpha\n",
        width=360,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
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
    previous_line_count = cast(  # noqa: SLF001
        Any, surface
    )._layout.frame.output.snapshot.line_count()

    QTest.keyClick(box, Qt.Key.Key_Backspace)

    assert box.toPlainText() == "alpha"
    assert rebuild_count == 0
    assert (
        cast(Any, surface)._layout.frame.output.snapshot.line_count()  # noqa: SLF001
        == previous_line_count - 1
    )
    assert surface.has_stale_projection_geometry() is False


def test_projection_surface_newline_backspace_flushes_pending_typing_before_delete(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Newline Backspace should not full-rebuild against stale typing geometry."""

    box = show_prompt_editor(
        widgets,
        text="alpha\nbeta",
        width=360,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
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

    QTest.keyClicks(box, "x")
    flush_semantic_refresh(box)

    assert surface.has_pending_projection_update() is True
    rebuild_count = 0
    cursor_position = box.toPlainText().index("\n") + 1
    surface._set_deferred_source_caret_states(  # noqa: SLF001
        cursor_state=PromptProjectionCaretState(source_position=cursor_position),
        anchor_state=PromptProjectionCaretState(source_position=cursor_position),
    )

    QTest.keyClick(box, Qt.Key.Key_Backspace)

    assert box.toPlainText() == "alphabetax"
    assert rebuild_count == 0
    assert surface.has_stale_projection_geometry() is False
    assert surface.has_pending_projection_update() is False

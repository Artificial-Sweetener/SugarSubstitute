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

"""Verify mounted surface scheduling and projection rebuild decisions."""

from __future__ import annotations

from typing import Any, cast

import pytest
from PySide6.QtGui import QFontMetricsF
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)
from tests.support.prompt_editor.projection_surface_support import (
    delay_projection_update_scheduler,
    first_emphasis_token,
    flush_semantic_refresh,
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
    valid_transient_insertion_overlay,
)
from tests.presentation.editor.prompt_editor.projection.update_scheduling.support import (
    _flush_projection_update_scheduler,
)


def test_projection_surface_default_scheduler_keeps_safe_typing_projection_pending(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default projection scheduling should keep safe typing off the keypress lane."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), ",
        width=240,
    )
    surface = surface_for(box)
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
    flush_semantic_refresh(box)

    assert box.toPlainText() == "(cat:1.05), x"
    assert rebuild_count == 0
    assert surface.has_pending_projection_update() is True


def test_projection_surface_layout_sync_preserves_safe_typing_overlay(
    widgets: list[QWidget],
) -> None:
    """Layout refreshes should not invalidate deferred typed text overlays."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), ",
        width=240,
    )
    surface = surface_for(box)
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )

    QTest.keyClicks(box, "x")

    overlay_before_sync = valid_transient_insertion_overlay(surface)
    assert overlay_before_sync is not None
    cast(Any, surface)._sync_layout_state()  # noqa: SLF001
    overlay_after_sync = valid_transient_insertion_overlay(surface)

    assert overlay_after_sync is not None
    assert overlay_after_sync.text == "x"


def test_projection_surface_refresh_geometry_does_not_emit_stale_safe_height(
    widgets: list[QWidget],
) -> None:
    """Passive geometry refresh should not publish old height during safe typing."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), ",
        width=240,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    emitted_heights: list[float] = []
    surface.contentHeightChanged.connect(emitted_heights.append)

    QTest.keyClicks(box, "x")
    flush_semantic_refresh(box)
    emitted_heights.clear()
    surface.refresh_geometry()

    assert emitted_heights == []
    assert surface.has_pending_projection_update() is True
    _flush_projection_update_scheduler(surface)


def test_projection_surface_schedules_semantics_after_syntax_sensitive_typing(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Token syntax edits should paint immediately and coalesce semantic catch-up."""

    box = show_prompt_editor(
        widgets,
        text="alpha",
        width=240,
    )
    surface = surface_for(box)
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

    QTest.keyClicks(box, "(")

    assert box.toPlainText() == "alpha("
    assert rebuild_count == 0
    assert surface.projection_document().source_text == "alpha("
    assert surface.has_pending_projection_update() is False
    assert surface.has_stale_projection_geometry() is False
    assert surface.cursor_position == len("alpha(")


def test_projection_surface_defers_normal_comma_typing(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Comma typing in ordinary prompt text should stay off the immediate rebuild path."""

    box = show_prompt_editor(
        widgets,
        text="alpha",
        width=240,
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

    QTest.keyClicks(box, ",")
    overlay = valid_transient_insertion_overlay(surface)
    assert overlay is not None
    assert overlay.text == ","
    flush_semantic_refresh(box)

    assert box.toPlainText() == "alpha,"
    assert rebuild_count == 0
    assert surface.has_pending_projection_update() is True

    _flush_projection_update_scheduler(surface)

    assert rebuild_count == 0
    assert valid_transient_insertion_overlay(surface) is None


def test_projection_surface_rebuilds_immediately_for_comma_inside_active_token(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Comma typing inside a focused projected syntax token should remain immediate."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=240,
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
    surface.set_cursor_positions(cursor_position=2, anchor_position=2)
    rebuild_count = 0

    QTest.keyClicks(box, ",")

    assert box.toPlainText() == "(c,at:1.05)"
    assert rebuild_count == 0
    assert surface.projection_document().source_text == box.toPlainText()
    assert surface.cursor_position == 3
    assert surface.has_pending_projection_update() is False


def test_projection_surface_coalesces_repeated_simple_typed_projection_rebuilds(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repeated trailing insertions should catch up without full relayout."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), ",
        width=240,
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

    QTest.keyClicks(box, "xy")
    overlay = valid_transient_insertion_overlay(surface)
    assert overlay is not None
    assert overlay.text == "xy"
    overlay_rect = cast(Any, surface)._transient_insertion_overlay_viewport_rect(
        overlay
    )
    expected_text_width = QFontMetricsF(box.font()).horizontalAdvance("xy")
    assert overlay_rect.width() == pytest.approx(expected_text_width)
    flush_semantic_refresh(box)

    assert box.toPlainText() == "(cat:1.05), xy"
    assert rebuild_count == 0
    assert surface.has_pending_projection_update() is True

    _flush_projection_update_scheduler(surface)
    process_events(app)

    assert first_emphasis_token(box).display_text == "cat"
    assert surface.projection_document().source_text == "(cat:1.05), xy"
    assert rebuild_count == 0
    assert valid_transient_insertion_overlay(surface) is None

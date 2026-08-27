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


import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from tests.support.prompt_editor.projection_engine_support import (
    show_prompt_editor,
    surface_for,
)
from tests.support.prompt_editor.projection_surface_support import (
    configure_trailing_word_wrap_boundary,
    delay_projection_update_scheduler,
    first_emphasis_token,
    flush_projection_update_scheduler,
    flush_semantic_refresh,
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
    valid_transient_insertion_overlay,
)
from tests.support.qt.semantic_wait import wait_for_qt_condition

from .support import (
    _projection_line_texts,
    _valid_transient_deletion_overlay,
)


def test_projection_surface_empty_middle_line_typing_uses_incremental_layout(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Typing into an empty middle line should not force a full projection rebuild."""

    box = show_prompt_editor(
        widgets,
        text="alpha\n\nomega",
        width=360,
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
    empty_line_position = box.toPlainText().index("\n\n") + 1
    surface.set_cursor_positions(
        cursor_position=empty_line_position,
        anchor_position=empty_line_position,
    )
    rebuild_count = 0

    QTest.keyClicks(box, "x")

    assert box.toPlainText() == "alpha\nx\nomega"
    assert surface.projection_document().source_text == "alpha\nx\nomega"
    assert rebuild_count == 0
    assert surface.has_stale_projection_geometry() is False
    assert _projection_line_texts(surface) == ("alpha", "x", "omega")


def test_projection_surface_middle_plain_backspace_publishes_real_layout(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Plain middle Backspace should reflow text instead of painting an erase block."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), alpha beta gamma",
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
    cursor_position = box.toPlainText().index(" beta")
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0
    upstream_token = first_emphasis_token(box)
    upstream_token_rect = surface._layout.frame.geometry.tokens.token_rect(  # noqa: SLF001
        upstream_token,
        scroll_offset=0.0,
    )
    assert upstream_token_rect is not None
    previous_height = surface.content_height()
    previous_scroll_maximum = surface.verticalScrollBar().maximum()

    QTest.keyClick(box, Qt.Key.Key_Backspace)

    assert box.toPlainText() == "(cat:1.05), alph beta gamma"
    assert rebuild_count <= 1
    assert surface.has_stale_projection_geometry() is False
    assert _valid_transient_deletion_overlay(surface) is None
    current_upstream_token = first_emphasis_token(box)
    current_upstream_token_rect = surface._layout.frame.geometry.tokens.token_rect(  # noqa: SLF001
        current_upstream_token,
        scroll_offset=0.0,
    )
    assert current_upstream_token_rect is not None
    assert current_upstream_token_rect == upstream_token_rect
    assert surface.content_height() <= previous_height
    assert surface.verticalScrollBar().maximum() <= previous_scroll_maximum

    height_after_backspace = surface.content_height()
    scroll_maximum_after_backspace = surface.verticalScrollBar().maximum()

    flush_semantic_refresh(box)

    assert rebuild_count <= 1
    assert surface.content_height() == pytest.approx(height_after_backspace)
    assert surface.verticalScrollBar().maximum() == scroll_maximum_after_backspace


def test_projection_surface_middle_plain_typing_publishes_real_layout(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Plain middle typing should reflow following text instead of overlaying it."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), alpha beta gamma",
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
    cursor_position = box.toPlainText().index(" beta")
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0
    upstream_token = first_emphasis_token(box)
    upstream_token_rect = surface._layout.frame.geometry.tokens.token_rect(  # noqa: SLF001
        upstream_token,
        scroll_offset=0.0,
    )
    assert upstream_token_rect is not None

    QTest.keyClicks(box, "x")

    assert box.toPlainText() == "(cat:1.05), alphax beta gamma"
    assert rebuild_count <= 1
    assert surface.has_stale_projection_geometry() is False
    assert valid_transient_insertion_overlay(surface) is None
    current_upstream_token = first_emphasis_token(box)
    current_upstream_token_rect = surface._layout.frame.geometry.tokens.token_rect(  # noqa: SLF001
        current_upstream_token,
        scroll_offset=0.0,
    )
    assert current_upstream_token_rect is not None
    assert current_upstream_token_rect == upstream_token_rect

    height_after_typing = surface.content_height()
    scroll_maximum_after_typing = surface.verticalScrollBar().maximum()

    flush_semantic_refresh(box)

    assert rebuild_count <= 1
    assert surface.content_height() == pytest.approx(height_after_typing)
    assert surface.verticalScrollBar().maximum() == scroll_maximum_after_typing


def test_projection_surface_word_edge_typing_keeps_word_wrap_integrity(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Typing at a wrap edge should coalesce reflow off the keypress lane."""

    box = show_prompt_editor(
        widgets,
        text="alpha beta bl",
        width=260,
    )
    surface = surface_for(box)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record wrap-boundary fallback rebuilds while preserving behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    configure_trailing_word_wrap_boundary(box, surface)

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    delay_projection_update_scheduler(surface)
    surface.set_cursor_positions(
        cursor_position=len(box.toPlainText()),
        anchor_position=len(box.toPlainText()),
    )
    rebuild_count = 0

    QTest.keyClicks(box, "ush")
    wait_for_qt_condition(
        lambda: (
            surface.has_pending_projection_update()
            and surface.has_stale_projection_geometry()
        ),
        description="delayed word-edge projection update",
        state=lambda: {
            "text": box.toPlainText(),
            "pending_projection": surface.has_pending_projection_update(),
            "stale_geometry": surface.has_stale_projection_geometry(),
            "rebuild_count": rebuild_count,
        },
    )

    assert surface.has_pending_projection_update() is True
    assert surface.has_stale_projection_geometry() is True
    assert rebuild_count == 0
    flush_projection_update_scheduler(surface)
    wait_for_qt_condition(
        lambda: (
            not surface.has_pending_projection_update()
            and not surface.has_stale_projection_geometry()
        ),
        description="flushed word-edge projection update",
        state=lambda: {
            "text": box.toPlainText(),
            "pending_projection": surface.has_pending_projection_update(),
            "stale_geometry": surface.has_stale_projection_geometry(),
            "rebuild_count": rebuild_count,
        },
    )

    line_texts = _projection_line_texts(surface)
    assert any("blush" in line_text for line_text in line_texts)
    assert not any(
        line_text.endswith("bl") and next_line_text.startswith("ush")
        for line_text, next_line_text in zip(line_texts, line_texts[1:], strict=False)
    )
    assert rebuild_count <= 1

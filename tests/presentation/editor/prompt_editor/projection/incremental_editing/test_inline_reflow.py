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
from PySide6.QtCore import QRect, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.prompt_editor.projection.incremental_edit_contracts import (
    PromptProjectionPlainTextApplyResult,
    PromptProjectionPlainTextApplyStatus,
)
from substitute.presentation.editor.prompt_editor.projection.source_edit_projection_policy import (
    PromptSourceEditProjectionDecision,
)
from substitute.presentation.editor.prompt_editor.projection.source_edit_projection_facts import (
    PromptSourceEditProjectionFactResolver,
)
from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)
from tests.support.prompt_editor.projection_surface_support import (
    delay_projection_update_scheduler,
    flush_projection_update_scheduler,
    flush_semantic_refresh,
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
    valid_transient_insertion_overlay,
)

from .support import (
    _valid_transient_deletion_overlay,
)


def test_projection_surface_applies_local_middle_comma_without_rebuild(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Local comma keep-group edits should avoid synchronous full rebuilds."""

    box = show_prompt_editor(
        widgets,
        text="test test test test, omega",
        width=1000,
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
    cursor_position = len("test")
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0

    QTest.keyClicks(box, ",")

    assert box.toPlainText() == "test, test test test, omega"
    assert rebuild_count == 0
    assert surface.has_pending_projection_update() is False
    assert surface.has_stale_projection_geometry() is False


def test_projection_surface_middle_typing_rejects_transient_overlay(
    widgets: list[QWidget],
) -> None:
    """Typing before existing live text should not paint a stale insertion overlay."""

    box = show_prompt_editor(
        widgets,
        text="alpha omega",
        width=360,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
    cursor_position = len("alpha ")
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )

    QTest.keyClicks(box, "x")

    assert box.toPlainText() == "alpha xomega"
    assert valid_transient_insertion_overlay(surface) is None
    assert surface.has_stale_projection_geometry() is False


def test_projection_surface_middle_typing_invalidates_backing_fill(
    widgets: list[QWidget],
) -> None:
    """Incremental middle typing should request host-owned background repaint."""

    box = show_prompt_editor(
        widgets,
        text="alpha omega",
        width=360,
    )
    surface = surface_for(box)
    invalidated_rects: list[QRect] = []
    surface.backingFillInvalidated.connect(invalidated_rects.append)
    cursor_position = len("alpha ")
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )

    QTest.keyClicks(box, "x")

    assert box.toPlainText() == "alpha xomega"
    assert invalidated_rects
    assert all(not rect.isEmpty() for rect in invalidated_rects)


def test_projection_surface_wrapped_visual_line_suffix_typing_uses_authoritative_geometry(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Typing before wrapped text should not use stale overlay geometry."""

    box = show_prompt_editor(
        widgets,
        text="alpha beta gamma delta epsilon zeta eta theta omega",
        width=150,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
    text = box.toPlainText()
    cursor_position = next(
        position
        for position in range(len(text))
        if cast(
            Any, surface
        )._layout.frame.geometry.caret.source_position_at_visual_line_content_end(
            position
        )
        and text[position] not in {"\n", "\r"}
    )
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0

    QTest.keyClicks(box, "xy")

    overlay = valid_transient_insertion_overlay(surface)
    assert overlay is None
    assert box.toPlainText() == f"{text[:cursor_position]}xy{text[cursor_position:]}"
    flush_semantic_refresh(box)

    if surface.has_pending_projection_update():
        flush_projection_update_scheduler(surface)
        process_events(ensure_qapp())

    assert rebuild_count <= 1
    assert surface.has_stale_projection_geometry() is False


def test_projection_surface_repeated_backspace_publishes_real_layout(
    widgets: list[QWidget],
) -> None:
    """Repeated plain backspace should not hide removed committed characters."""

    box = show_prompt_editor(
        widgets,
        text="alpha",
        width=360,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )

    QTest.keyClick(box, Qt.Key.Key_Backspace)
    QTest.keyClick(box, Qt.Key.Key_Backspace)

    overlay = _valid_transient_deletion_overlay(surface)
    assert box.toPlainText() == "alp"
    assert overlay is None
    assert surface.has_stale_projection_geometry() is False


def test_projection_surface_fallback_backspace_uses_canonical_reflow_without_overlay(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backspace should publish canonical state when transient paths are unavailable."""

    box = show_prompt_editor(
        widgets,
        text="alpha beta",
        width=360,
    )
    surface = surface_for(box)
    if surface.has_pending_projection_update():
        flush_projection_update_scheduler(surface)
        process_events(ensure_qapp())
    delay_projection_update_scheduler(surface)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    monkeypatch.setattr(
        PromptSourceEditProjectionFactResolver,
        "resolve",
        lambda _self, **_kwargs: PromptSourceEditProjectionDecision(
            can_defer_projection=False,
            deferral_reason="test_forced_immediate_fallback",
        ),
    )
    monkeypatch.setattr(
        cast(Any, surface)._edit_pipeline._trailing_strategy,
        "try_plain_delete",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        cast(Any, surface)._edit_pipeline._trailing_strategy,
        "try_newline_delete",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        cast(Any, surface)._edit_pipeline._reflow_strategy,
        "try_incremental",
        lambda **_kwargs: PromptProjectionPlainTextApplyResult(
            status=PromptProjectionPlainTextApplyStatus.REJECTED
        ),
    )
    monkeypatch.setattr(
        cast(Any, surface)._edit_pipeline._deferred_strategy,
        "try_defer_fallback",
        lambda _request: False,
    )
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )

    QTest.keyClick(box, Qt.Key.Key_Backspace)
    first_overlay = _valid_transient_deletion_overlay(surface)
    QTest.keyClick(box, Qt.Key.Key_Backspace)
    second_overlay = _valid_transient_deletion_overlay(surface)

    assert box.toPlainText() == "alpha be"
    assert first_overlay is None
    assert second_overlay is None
    assert surface.has_pending_projection_update() is False
    assert surface.has_stale_projection_geometry() is False
    assert surface.projection_document().source_text == "alpha be"
    assert surface.cursor_position == len("alpha be")
    assert rebuild_count == 0

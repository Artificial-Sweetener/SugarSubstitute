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

from substitute.presentation.editor.prompt_editor.projection.render_frame import (
    PromptProjectionContentPaintMode,
)
from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)
from tests.support.prompt_editor.projection_surface_support import (
    delay_projection_update_scheduler,
    first_emphasis_token,
    flush_projection_update_scheduler,
    flush_semantic_refresh,
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
    render_surface_viewport,
    valid_transient_insertion_overlay,
)

from .support import (
    _projection_line_texts,
    _valid_transient_deletion_overlay,
)


def test_projection_surface_kept_tag_edit_uses_fast_path_when_layout_stays_local(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Kept tag edits should stay fast when the group remains on its line."""

    box = show_prompt_editor(
        widgets,
        text="alpha beta, cowgirl po, omega",
        width=520,
    )
    surface = surface_for(box)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record fallback rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    cursor_position = box.toPlainText().index("po") + 2
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)

    QTest.keyClicks(box, "s")

    assert box.toPlainText() == "alpha beta, cowgirl pos, omega"
    assert rebuild_count == 0


def test_projection_surface_kept_tag_edge_edit_uses_projection_reuse_fallback(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Kept tag edge edits should coalesce wrap reflow off the keypress lane."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="alpha beta, cowgirl po, omega",
        width=260,
    )
    surface = surface_for(box)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record fallback rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    configured_width: int | None = None
    for width in range(190, 421, 5):
        box.setGeometry(20, 20, width, box.height())
        process_events(app)
        if any(
            line_text.strip().endswith("cowgirl po,")
            for line_text in _projection_line_texts(surface)
        ):
            configured_width = width
            break
    assert configured_width is not None

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    delay_projection_update_scheduler(surface)
    cursor_position = box.toPlainText().index("po") + 2
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )

    QTest.keyClicks(box, "s")
    process_events(app)

    assert box.toPlainText() == "alpha beta, cowgirl pos, omega"
    if surface.has_pending_projection_update():
        assert surface.has_stale_projection_geometry() is True
        flush_projection_update_scheduler(surface)
        process_events(app)
    else:
        assert surface.has_stale_projection_geometry() is False

    assert any(
        "cowgirl pos," in line_text for line_text in _projection_line_texts(surface)
    )
    assert rebuild_count <= 1


def test_projection_surface_projected_token_delete_preserves_unaffected_tokens(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deleting inside one projected token should not make the whole prompt raw."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), alpha, (dog:1.10)",
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
    cursor_position = box.toPlainText().index("t:")
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0

    QTest.keyClick(box, Qt.Key.Key_Backspace)

    projected_texts = {
        token.display_text for token in surface.projection_document().tokens
    }
    assert box.toPlainText() == "(ct:1.05), alpha, (dog:1.10)"
    assert "dog" in projected_texts
    assert surface.projection_document().source_text == box.toPlainText()
    assert surface.cursor_position == cursor_position - 1
    assert rebuild_count == 0
    assert surface.has_stale_projection_geometry() is False


def test_projection_surface_source_edit_rejects_stale_content_by_revision(
    widgets: list[QWidget],
) -> None:
    """Source edits should replace cache identity without manual invalidation."""

    box = show_prompt_editor(
        widgets,
        text="alpha beta",
        width=360,
    )
    surface = surface_for(box)
    render_surface_viewport(surface)
    compositor = cast(Any, surface)._render_compositor
    initial_cache = compositor.content_cache_snapshot
    assert initial_cache.key is not None
    assert initial_cache.has_pixmap

    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    QTest.keyClick(box, Qt.Key.Key_Backspace)

    assert box.toPlainText() == "alpha bet"
    retained_cache = compositor.content_cache_snapshot
    assert retained_cache.key is not None
    current_paint = cast(Any, surface).editor_state.current_paint
    assert current_paint is not None
    assert retained_cache.key.paint_identity in {
        initial_cache.key.paint_identity,
        current_paint.identity,
    }

    render_surface_viewport(surface)

    refreshed_cache = compositor.content_cache_snapshot
    assert refreshed_cache.key is not None
    assert refreshed_cache.key.paint_identity is current_paint.identity


def test_projection_surface_transient_edit_reuses_valid_content_cache(
    widgets: list[QWidget],
) -> None:
    """Stale-safe feedback must retain and reuse the valid base content cache."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), ",
        width=360,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
    render_surface_viewport(surface)
    compositor = cast(Any, surface)._render_compositor
    initial_cache = compositor.content_cache_snapshot
    assert initial_cache.key is not None
    assert initial_cache.has_pixmap
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )

    QTest.keyClicks(box, "xy")

    frame = cast(Any, surface)._render_frame_owner.frame
    assert frame.content_mode is PromptProjectionContentPaintMode.CACHED
    assert frame.transient_layer.insertion is not None
    render_surface_viewport(surface)
    assert compositor.content_cache_snapshot == initial_cache


def test_projection_surface_terminal_separator_continues_one_transient_insertion(
    widgets: list[QWidget],
) -> None:
    """Typing after a completed terminal separator must retain the whole edit chain."""

    box = show_prompt_editor(
        widgets,
        text="global\n[SEP]\n[SEP",
        width=360,
    )
    surface = surface_for(box)
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )

    QTest.keyClicks(box, "]")
    assert box.toPlainText() == "global\n[SEP]\n[SEP]\n"
    QTest.keyClicks(box, "j")
    first_overlay = valid_transient_insertion_overlay(surface)
    assert first_overlay is not None
    assert first_overlay.text == "j"
    QTest.keyClicks(box, "f")

    second_overlay = valid_transient_insertion_overlay(surface)
    assert second_overlay is not None
    assert second_overlay.source_start == len("global\n[SEP]\n[SEP]\n")
    assert second_overlay.text == "jf"


def test_projection_surface_backspace_updates_for_immediate_visibility(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trailing plain deletion should publish real layout without an erase overlay."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), alpha",
        width=360,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
    committed_height = surface.content_height()
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    original_ensure_caret_visible = surface._ensure_caret_visible  # noqa: SLF001
    original_collapse_expanded_token = (  # noqa: SLF001
        surface._collapse_expanded_token_if_possible  # noqa: SLF001
    )
    rebuild_count = 0
    ensure_caret_visible_count = 0
    collapse_expanded_token_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    def count_ensure_caret_visible() -> None:
        """Record caret visibility sync calls while preserving behavior."""

        nonlocal ensure_caret_visible_count
        ensure_caret_visible_count += 1
        original_ensure_caret_visible()

    def count_collapse_expanded_token() -> None:
        """Record expanded-token collapse checks while preserving behavior."""

        nonlocal collapse_expanded_token_count
        collapse_expanded_token_count += 1
        original_collapse_expanded_token()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    monkeypatch.setattr(surface, "_ensure_caret_visible", count_ensure_caret_visible)
    monkeypatch.setattr(
        surface,
        "_collapse_expanded_token_if_possible",
        count_collapse_expanded_token,
    )
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0
    ensure_caret_visible_count = 0
    collapse_expanded_token_count = 0

    QTest.keyClick(box, Qt.Key.Key_Backspace)

    assert box.toPlainText() == "(cat:1.05), alph"
    assert surface.has_stale_projection_geometry() is False
    assert _valid_transient_deletion_overlay(surface) is None
    assert rebuild_count == 0
    assert ensure_caret_visible_count == 1
    assert collapse_expanded_token_count == 0
    assert surface.content_height() == pytest.approx(committed_height)
    assert surface.has_pending_projection_update() is False
    assert first_emphasis_token(box).display_text == "cat"
    committed_metrics = cast(
        Any, surface
    )._projection_freshness_controller.committed_metrics
    assert committed_metrics is not None
    assert (
        committed_metrics.source_revision == surface.editor_state.source.source_revision
    )


def test_projection_surface_expanded_token_enter_preserves_semantic_projection(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Enter while a token is expanded should not publish an all-raw interim layout."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), alpha beta, (dog:1.10)",
        width=360,
    )
    surface = surface_for(box)
    expanded_token = first_emphasis_token(box)
    surface._session.expand_token(expanded_token)  # noqa: SLF001
    surface._rebuild_projection()  # noqa: SLF001
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

    QTest.keyClick(box, Qt.Key.Key_Return)

    projected_texts = {
        token.display_text for token in surface.projection_document().tokens
    }
    assert box.toPlainText() == "(cat:1.05), alpha\n beta, (dog:1.10)"
    assert "dog" in projected_texts
    assert surface.has_stale_projection_geometry() is False
    assert surface.projection_document().source_text == box.toPlainText()
    assert surface.cursor_position == cursor_position + 1
    assert rebuild_count == 0

    content_height_after_enter = surface.content_height()
    flush_semantic_refresh(box)

    refreshed_texts = {
        token.display_text for token in surface.projection_document().tokens
    }
    assert "dog" in refreshed_texts
    assert surface.content_height() == pytest.approx(content_height_after_enter)
    assert surface.projection_document().source_text == box.toPlainText()
    assert surface.cursor_position == cursor_position + 1
    assert rebuild_count == 0


def test_projection_surface_expanded_token_newline_backspace_preserves_semantics(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Newline Backspace with an expanded token should avoid all-raw interim layout."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), alpha\n beta, (dog:1.10)",
        width=360,
    )
    surface = surface_for(box)
    expanded_token = first_emphasis_token(box)
    surface._session.expand_token(expanded_token)  # noqa: SLF001
    surface._rebuild_projection()  # noqa: SLF001
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    cursor_position = box.toPlainText().index("\n") + 1
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0

    QTest.keyClick(box, Qt.Key.Key_Backspace)

    projected_texts = {
        token.display_text for token in surface.projection_document().tokens
    }
    assert box.toPlainText() == "(cat:1.05), alpha beta, (dog:1.10)"
    assert "dog" in projected_texts
    assert surface.has_stale_projection_geometry() is False
    assert surface.projection_document().source_text == box.toPlainText()
    assert surface.cursor_position == cursor_position - 1
    assert rebuild_count == 0

    content_height_after_backspace = surface.content_height()
    flush_semantic_refresh(box)

    refreshed_texts = {
        token.display_text for token in surface.projection_document().tokens
    }
    assert "dog" in refreshed_texts
    assert surface.content_height() == pytest.approx(content_height_after_backspace)
    assert surface.projection_document().source_text == box.toPlainText()
    assert surface.cursor_position == cursor_position - 1
    assert rebuild_count == 0


def test_projection_surface_backspace_rebuilds_after_pending_typing_projection(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backspace should safely commit geometry after deferred typing is removed."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), ",
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

    QTest.keyClicks(box, "x")
    flush_semantic_refresh(box)
    assert surface.has_pending_projection_update() is True

    QTest.keyClick(box, Qt.Key.Key_Backspace)

    assert box.toPlainText() == "(cat:1.05), "
    assert rebuild_count == 1
    assert valid_transient_insertion_overlay(surface) is None
    assert surface.has_pending_projection_update() is False
    assert surface.has_stale_projection_geometry() is False
    assert rebuild_count == 1
    committed_metrics = cast(
        Any, surface
    )._projection_freshness_controller.committed_metrics
    assert committed_metrics is not None
    assert (
        committed_metrics.source_revision == surface.editor_state.source.source_revision
    )

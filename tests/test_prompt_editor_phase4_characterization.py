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

"""Characterize Phase 4 geometry, shell, command, and scheduling behavior."""

from __future__ import annotations

from collections.abc import Iterator
import os
from time import perf_counter
from typing import Any, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter, QPixmap, QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.prompt_editor import (
    PromptDiagnostic,
    PromptDiagnosticKind,
    PromptDiagnosticSeverity,
    PromptSpellingDiagnosticPayload,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.autocomplete_preview_state import (
    PromptAutocompletePreviewState,
)
from substitute.presentation.editor.prompt_editor.projection.surface import (
    PromptProjectionSurface,
)
from tests.prompt_projection_test_helpers import (
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "phase 4 prompt editor characterization tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


@pytest.fixture()
def widgets() -> Iterator[list[QWidget]]:
    """Track widgets created by one Phase 4 characterization test."""

    created: list[QWidget] = []
    yield created
    app = ensure_qapp()
    for widget in reversed(created):
        widget.close()
        widget.deleteLater()
    process_events(app)


def test_phase4_layout_wrap_fragments_caret_and_width_reflow(
    widgets: list[QWidget],
) -> None:
    """Wrapped projection geometry should stay source-backed across width changes."""

    text = (
        "alpha beta gamma delta epsilon zeta eta theta iota kappa, "
        "<lora:demo:0.80>, {animal|2}, (blue sky:1.20)\n\nomega"
    )
    box = _show_phase4_editor(widgets, text=text, width=230)
    surface = surface_for(box)
    surface.set_source_line_content_left_inset(28.0)
    process_events(ensure_qapp())

    first_line_end = text.index("\n")
    narrow_height = surface.content_height()
    first_line_fragments = surface.source_range_fragments(start=0, end=first_line_end)
    lora_fragments = surface.source_range_fragments(
        start=text.index("<lora"),
        end=text.index(">") + 1,
    )
    wildcard_fragments = surface.source_range_fragments(
        start=text.index("{animal"),
        end=text.index("{animal|2}") + len("{animal|2}"),
    )
    emphasis_fragments = surface.source_range_fragments(
        start=text.index("(blue"),
        end=text.index(")") + 1,
    )

    blank_line_position = text.index("\n\n") + 1
    surface.set_cursor_positions(
        cursor_position=blank_line_position,
        anchor_position=blank_line_position,
    )
    blank_caret = box.cursorRect()
    expected_content_left = (
        cast(float, cast(Any, surface)._layout.document_margin) + 28.0
    )

    box.setGeometry(box.x(), box.y(), 520, box.height())
    process_events(ensure_qapp(), cycles=10)
    wide_height = surface.content_height()

    assert len(first_line_fragments) >= 2
    assert lora_fragments
    assert wildcard_fragments
    assert emphasis_fragments
    assert blank_caret.x() == pytest.approx(expected_content_left, abs=1.0)
    assert wide_height < narrow_height
    assert box.toPlainText() == text


def test_phase4_shell_placeholder_scrollbar_focus_and_size_facade(
    widgets: list[QWidget],
) -> None:
    """The PromptEditor shell should expose source-backed facade and scroll state."""

    box = _show_phase4_editor(widgets, text="", width=360)
    box.setPlaceholderText("Describe the image")
    process_events(ensure_qapp())

    assert box.placeholderText() == "Describe the image"
    assert box.toPlainText() == ""
    assert box.sizeHint().height() == box.height()
    assert box.minimumSizeHint().height() == box.height()

    box.setPlainText("\n".join(f"line {index}" for index in range(50)))
    box.setFocus()
    process_events(ensure_qapp(), cycles=10)
    scroll_bar = box.verticalScrollBar()
    scroll_delegate = cast(Any, getattr(box, "scrollDelegate"))
    visible_scroll_bar = scroll_delegate.vScrollBar

    scroll_bar.setValue(scroll_bar.maximum())
    process_events(ensure_qapp())

    assert box.hasFocus()
    assert scroll_bar.maximum() > 0
    assert visible_scroll_bar.partnerBar is scroll_bar
    assert visible_scroll_bar.maximum() == scroll_bar.maximum()
    assert visible_scroll_bar.pageStep() == scroll_bar.pageStep()
    assert visible_scroll_bar.value() == scroll_bar.value()
    assert cast(Any, box)._surface is surface_for(box)


def test_phase4_clipboard_commands_preserve_source_cursor_and_undo(
    widgets: list[QWidget],
) -> None:
    """Clipboard commands should operate on raw source text and undo as one edit."""

    app = ensure_qapp()
    clipboard = QApplication.clipboard()
    previous_clipboard_text = clipboard.text()
    text = "alpha, <lora:demo:0.80>, {animal|2}, (blue sky:1.20)"
    box = _show_phase4_editor(widgets, text=text, width=420)
    try:
        lora_start = text.index("<lora")
        lora_end = text.index(">") + 1
        _select_source_range(box, lora_start, lora_end)

        box.copy()
        assert clipboard.text() == "<lora:demo:0.80>"
        assert box.toPlainText() == text
        assert box.textCursor().selectionStart() == lora_start
        assert box.textCursor().selectionEnd() == lora_end

        box.cut()
        process_events(app)
        assert clipboard.text() == "<lora:demo:0.80>"
        assert box.toPlainText() == "alpha, , {animal|2}, (blue sky:1.20)"
        assert box.textCursor().position() == lora_start
        assert box.textCursor().selectionStart() == lora_start
        assert box.textCursor().selectionEnd() == lora_start

        box.undo()
        process_events(app)
        assert box.toPlainText() == text

        wildcard_start = text.index("{animal")
        wildcard_end = wildcard_start + len("{animal|2}")
        _select_source_range(box, wildcard_start, wildcard_end)
        clipboard.setText("beta")
        box.paste()
        process_events(app)
        assert box.toPlainText() == ("alpha, <lora:demo:0.80>, beta, (blue sky:1.20)")
        assert box.textCursor().selectionStart() == wildcard_start + len("beta")
        assert box.textCursor().selectionEnd() == wildcard_start + len("beta")

        box.undo()
        process_events(app)
        assert box.toPlainText() == text

        cast(Any, box).selectAll()
        assert box.textCursor().selectionStart() == 0
        assert box.textCursor().selectionEnd() == len(text)
    finally:
        clipboard.setText(previous_clipboard_text)


def test_phase4_search_and_source_line_chrome_track_projection_state(
    widgets: list[QWidget],
) -> None:
    """Search and source-line chrome should stay aligned with projection geometry."""

    text = "alpha beta\n<lora:demo:0.80>, alpha\n{animal|2}, (alpha sky:1.20)"
    box = _show_phase4_editor(widgets, text=text, width=360)
    surface = surface_for(box)
    alpha_ranges = tuple(
        (index, len("alpha"))
        for index in (
            text.index("alpha"),
            text.index("alpha", text.index("\n") + 1),
            text.rindex("alpha"),
        )
    )
    box.set_search_matches(alpha_ranges, active_index=1)
    box.set_source_line_chrome_enabled(True)
    box.set_source_line_content_left_inset(34.0)
    process_events(ensure_qapp())

    second_line_start = text.index("\n") + 1
    surface.set_cursor_positions(
        cursor_position=second_line_start,
        anchor_position=second_line_start,
    )
    source_line_rects = box.source_line_rects()
    before_scroll_tops = tuple(rect.rect.top() for rect in source_line_rects)
    chrome = cast(Any, surface)._source_line_chrome
    inactive_color = chrome.search_match_color(surface.palette(), active=False)
    active_color = chrome.search_match_color(surface.palette(), active=True)

    diagnostic = _spelling_diagnostic(text.rindex("alpha"), text.rindex("alpha") + 5)
    surface.set_diagnostics((diagnostic,))
    surface.set_autocomplete_preview_state(
        PromptAutocompletePreviewState(
            source_position=text.index("beta") + len("beta"),
            suffix_text=", sharp focus",
        )
    )
    pixmap = QPixmap(surface.viewport().size())
    surface.viewport().render(pixmap)

    box.verticalScrollBar().setValue(min(box.verticalScrollBar().maximum(), 20))
    process_events(ensure_qapp())
    after_scroll_tops = tuple(rect.rect.top() for rect in box.source_line_rects())

    assert cast(Any, surface)._session.search_match_ranges == alpha_ranges
    assert cast(Any, surface)._session.active_search_match_index == 1
    assert active_color.alpha() > inactive_color.alpha()
    assert len(source_line_rects) >= 3
    assert box.current_source_line_index() == 1
    assert cast(float, chrome.content_left_inset) == 34.0
    assert source_line_rects[0].rect.left() == pytest.approx(0.0, abs=1.0)
    assert cast(Any, surface)._session.diagnostics == (diagnostic,)
    assert cast(Any, surface)._session.autocomplete_preview is not None
    assert not pixmap.isNull()
    if box.verticalScrollBar().maximum() > 0:
        assert after_scroll_tops != before_scroll_tops


def test_phase4_source_line_chrome_tracks_scroll_for_long_prompts(
    widgets: list[QWidget],
) -> None:
    """Source-line chrome rows should move with the projection viewport scroll."""

    lines = [
        f"scene {index}, alpha beta gamma delta epsilon zeta repeated detail"
        for index in range(40)
    ]
    text = "\n".join(lines)
    box = _show_phase4_editor(widgets, text=text, width=320)
    box.setGeometry(box.x(), box.y(), 320, box.minimumEditorHeight() * 4)
    box.set_source_line_chrome_enabled(True)
    box.set_source_line_content_left_inset(32.0)
    process_events(ensure_qapp(), cycles=10)
    scroll_bar = box.verticalScrollBar()
    before_rects = box.source_line_rects()
    before_tops = tuple(rect.rect.top() for rect in before_rects)

    scroll_bar.setValue(min(scroll_bar.maximum(), max(1, box.lineHeight() * 3)))
    process_events(ensure_qapp(), cycles=10)
    after_rects = box.source_line_rects()
    after_tops = tuple(rect.rect.top() for rect in after_rects)

    assert scroll_bar.maximum() > 0
    assert before_rects
    assert after_rects
    assert after_tops != before_tops
    assert after_tops[0] < before_tops[0]
    assert cast(Any, surface_for(box))._source_line_chrome.content_left_inset == 32.0


def test_phase4_paint_composition_uses_preview_layout_and_suppresses_caret_for_selection(
    widgets: list[QWidget],
) -> None:
    """Overlapping paint layers should keep their current ordering contracts observable."""

    text = "<lora:demo:0.80>, {animal|2}, blue alpha, typo"
    box = _show_phase4_editor(widgets, text=text, width=360)
    surface = surface_for(box)
    typo_start = text.index("typo")
    alpha_start = text.index("alpha")
    surface.set_cursor_positions(
        cursor_position=alpha_start, anchor_position=alpha_start
    )
    surface.set_search_matches(
        ((text.index("animal"), len("animal")), (typo_start, len("typo"))),
        active_index=1,
    )
    surface.set_diagnostics((_spelling_diagnostic(typo_start, len(text)),))
    surface.set_autocomplete_preview_state(
        PromptAutocompletePreviewState(
            source_position=alpha_start,
            suffix_text=", sharp focus",
        )
    )
    active_projection_document = cast(Any, surface).active_projection_document()
    pixmap = QPixmap(surface.viewport().size())
    painter = QPainter(pixmap)
    try:
        projection_paint_result = cast(Any, surface)._paint_projection_content(
            painter,
            selection=cast(Any, surface)._selection(),
            scroll_offset=cast(float, cast(Any, surface)._scroll_offset()),
            clip_rect=QRectF(surface.viewport().rect()),
            viewport_rect=QRectF(surface.viewport().rect()),
            excluded_region=None,
        )
    finally:
        painter.end()

    _select_source_range(box, text.index("blue"), alpha_start + len("alpha"))
    selected_pixmap = QPixmap(surface.viewport().size())
    surface.viewport().render(selected_pixmap)

    assert ", sharp focus" in active_projection_document.projection_text
    assert projection_paint_result == "preview"
    assert cast(Any, surface)._projection_paint_cache.cache_key is None
    assert (
        cast(Any, surface)
        ._source_line_chrome.search_match_color(surface.palette(), active=True)
        .alpha()
        > cast(Any, surface)
        ._source_line_chrome.search_match_color(surface.palette(), active=False)
        .alpha()
    )
    assert cast(Any, surface)._session.diagnostics
    assert cast(Any, surface)._should_paint_caret() is False
    assert not selected_pixmap.isNull()


def test_phase4_clearing_autocomplete_preview_restores_base_projection_layout(
    widgets: list[QWidget],
) -> None:
    """Clearing ghost text must make the painted layout own the canonical document."""

    text = "alpha\n\nbackpack\n\nomega"
    box = _show_phase4_editor(widgets, text=text, width=360)
    surface = surface_for(box)
    cursor_position = text.index("backpack") + len("backpack")
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    surface.set_autocomplete_preview_state(
        PromptAutocompletePreviewState(
            source_position=cursor_position,
            suffix_text=" basket",
        )
    )
    assert (
        "backpack basket"
        in cast(Any, surface).active_projection_document().projection_text
    )
    assert (
        "backpack basket"
        in cast(Any, surface)._layout.projection_document.projection_text
    )

    surface.set_autocomplete_preview_state(None)

    assert cast(Any, surface)._session.autocomplete_preview is None
    assert (
        "backpack basket"
        not in cast(Any, surface).active_projection_document().projection_text
    )
    assert (
        cast(Any, surface)._layout.projection_document
        is cast(Any, surface).projection_document()
    )
    assert (
        "backpack basket"
        not in cast(Any, surface)._layout.projection_document.projection_text
    )
    pixmap = QPixmap(surface.viewport().size())
    painter = QPainter(pixmap)
    try:
        cast(Any, surface)._paint_projection_content(
            painter,
            selection=cast(Any, surface)._selection(),
            scroll_offset=cast(float, cast(Any, surface)._scroll_offset()),
            clip_rect=QRectF(surface.viewport().rect()),
            viewport_rect=QRectF(surface.viewport().rect()),
            excluded_region=None,
        )
    finally:
        painter.end()

    cache_key = cast(Any, surface)._projection_paint_cache.cache_key
    assert cache_key is None or not cache_key.paint_state.ghosted_run_ids


def test_phase4_projection_scheduling_and_small_repaint_paths_are_scoped(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Common safe edits should coalesce projection work and preserve small repaint paths."""

    app = ensure_qapp()
    box = _show_phase4_editor(widgets, text="alpha beta bl", width=260)
    surface = surface_for(box)
    original_rebuild_projection = cast(Any, surface)._rebuild_projection
    rebuild_count = 0

    def count_rebuild_projection() -> None:
        """Record full projection rebuilds while preserving behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild_projection)
    configured_width: int | None = None
    for width in range(145, 321, 5):
        box.setGeometry(20, 20, width, box.height())
        process_events(app)
        line_texts = _projection_line_texts(surface)
        if len(line_texts) == 1 and line_texts[0].endswith("bl"):
            configured_width = width
            break
    assert configured_width is not None

    _delay_projection_update_scheduler(surface)
    source_end = len(box.toPlainText())
    surface.set_cursor_positions(cursor_position=source_end, anchor_position=source_end)
    QTest.keyClicks(box, "ush")
    process_events(app)

    assert surface.has_pending_projection_update() is True
    assert surface.has_stale_projection_geometry() is True
    assert rebuild_count == 0
    _flush_projection_update_scheduler(surface)
    assert surface.has_pending_projection_update() is False
    assert rebuild_count <= 1

    pixmap = QPixmap(surface.viewport().size())
    painter = QPainter(pixmap)
    try:
        result = cast(Any, surface)._paint_projection_content(
            painter,
            selection=cast(Any, surface)._selection(),
            scroll_offset=cast(float, cast(Any, surface)._scroll_offset()),
            clip_rect=QRectF(0.0, 0.0, 8.0, 8.0),
            viewport_rect=QRectF(surface.viewport().rect()),
            excluded_region=None,
        )
    finally:
        painter.end()

    assert result in {"bypass_small_cache_miss", "bypass"}
    assert any("blush" in line_text for line_text in _projection_line_texts(surface))
    assert box.toPlainText() == "alpha beta blush"


def test_phase4_large_prompt_typing_scrolling_and_selection_stay_within_threshold(
    widgets: list[QWidget],
) -> None:
    """Representative large prompts should stay inside conservative local envelopes."""

    app = ensure_qapp()
    line = (
        "best quality, detailed lighting, layered background, "
        "<lora:demo:0.80>, {animal|2}, (blue sky:1.20)"
    )
    text = "\n".join(line for _ in range(120))
    box = _show_phase4_editor(widgets, text=text, width=520)
    box.setGeometry(box.x(), box.y(), 520, box.minimumEditorHeight() * 5)
    process_events(app, cycles=10)
    surface = surface_for(box)

    start = perf_counter()
    cursor = box.textCursor()
    cursor.setPosition(len(text), QTextCursor.MoveMode.MoveAnchor)
    box.setTextCursor(cursor)
    QTest.keyClicks(box, ", sharp")
    process_events(app, cycles=10)
    typing_ms = (perf_counter() - start) * 1000.0

    start = perf_counter()
    scroll_bar = box.verticalScrollBar()
    for fraction in (0.25, 0.5, 0.75, 1.0):
        scroll_bar.setValue(int(scroll_bar.maximum() * fraction))
        process_events(app)
    scrolling_ms = (perf_counter() - start) * 1000.0

    start = perf_counter()
    selection_cursor = box.textCursor()
    selection_cursor.setPosition(0, QTextCursor.MoveMode.MoveAnchor)
    selection_cursor.setPosition(
        min(len(box.toPlainText()), 800), QTextCursor.MoveMode.KeepAnchor
    )
    box.setTextCursor(selection_cursor)
    fragments = surface.source_range_fragments(start=0, end=800)
    selection_ms = (perf_counter() - start) * 1000.0

    assert box.toPlainText().endswith(", sharp")
    assert scroll_bar.maximum() > 0
    assert fragments
    assert typing_ms < 5_000.0
    assert scrolling_ms < 1500.0
    assert selection_ms < 500.0


def _show_phase4_editor(
    widgets: list[QWidget],
    *,
    text: str,
    width: int,
) -> PromptEditor:
    """Create one visible prompt editor configured for Phase 4 coverage."""

    return show_prompt_editor(
        widgets,
        text=text,
        width=width,
        syntaxes=("emphasis", "wildcard", "lora"),
    )


def _select_source_range(box: PromptEditor, start: int, end: int) -> None:
    """Select an exact raw source range on a prompt editor."""

    cursor = box.textCursor()
    cursor.setPosition(start, QTextCursor.MoveMode.MoveAnchor)
    cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
    box.setTextCursor(cursor)
    process_events(ensure_qapp())


def _delay_projection_update_scheduler(surface: PromptProjectionSurface) -> None:
    """Make projection scheduling observable without waiting for real time."""

    scheduler = cast(Any, surface)._projection_freshness_controller.update_scheduler
    scheduler._fixed_interval_ms = 1000
    scheduler._interval_ms = 1000
    scheduler._timer.setInterval(1000)


def _flush_projection_update_scheduler(surface: PromptProjectionSurface) -> None:
    """Flush delayed projection work through the production scheduler."""

    cast(Any, surface)._projection_freshness_controller.update_scheduler.flush_now(
        reason="test"
    )


def _projection_line_texts(surface: PromptProjectionSurface) -> tuple[str, ...]:
    """Return visible text grouped by projection visual line."""

    snapshot = cast(Any, surface)._layout._snapshot
    return tuple(
        "".join(
            fragment.text for fragment in line.fragments if hasattr(fragment, "text")
        )
        for line in snapshot.lines
    )


def _spelling_diagnostic(source_start: int, source_end: int) -> PromptDiagnostic:
    """Return one deterministic spelling diagnostic for source-range composition."""

    return PromptDiagnostic(
        diagnostic_id=f"spelling:{source_start}:{source_end}:alpha",
        kind=PromptDiagnosticKind.SPELLING,
        severity=PromptDiagnosticSeverity.ERROR,
        source_start=source_start,
        source_end=source_end,
        message="Possible spelling issue: alpha",
        payload=PromptSpellingDiagnosticPayload(word="alpha"),
    )

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

"""Tests for prompt projection diagnostic rendering and source remapping."""

from __future__ import annotations

import os
from dataclasses import replace
from typing import Any, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor import (
    PromptDiagnostic,
    PromptDiagnosticKind,
    PromptDiagnosticSeverity,
    PromptSpellingDiagnosticPayload,
    PromptWildcardDiagnosticPayload,
)
from substitute.presentation.editor.prompt_editor.projection.model import (
    PromptProjectionDisplayMode,
)
from tests.prompt_projection_test_helpers import (
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)
from tests.prompt_projection_surface_test_helpers import (
    apply_source_range_to_projection,
    delay_projection_update_scheduler,
    flush_projection_update_scheduler,
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
    render_surface_viewport,
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "projection surface tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


def _changed_pixel_distance(before: QImage, after: QImage, x: int, y: int) -> int:
    """Return the channel distance between two rendered pixels."""

    first = before.pixelColor(x, y)
    second = after.pixelColor(x, y)
    return (
        abs(first.red() - second.red())
        + abs(first.green() - second.green())
        + abs(first.blue() - second.blue())
        + abs(first.alpha() - second.alpha())
    )


def _diagnostic_column_centers(
    before: QImage,
    after: QImage,
    fragment: QRectF,
) -> tuple[float, ...]:
    """Return per-column centers of pixels introduced by a spelling diagnostic."""

    left = max(0, int(fragment.left()) - 1)
    right = min(after.width() - 1, int(fragment.right()) + 1)
    top = max(0, int(fragment.bottom()) - 8)
    bottom = min(after.height() - 1, int(fragment.bottom()) + 2)
    centers: list[float] = []
    for x in range(left, right + 1):
        changed_rows = [
            y
            for y in range(top, bottom + 1)
            if _changed_pixel_distance(before, after, x, y) > 24
        ]
        if changed_rows:
            centers.append(sum(changed_rows) / len(changed_rows))
    return tuple(centers)


def test_projection_surface_diagnostic_renders_wavy_error_underline(
    widgets: list[QWidget],
) -> None:
    """Prompt diagnostics should render as a wavy semantic-error underline."""

    app = ensure_qapp()
    word = "missspelledword"
    box = show_prompt_editor(
        widgets,
        text=word,
        width=360,
    )
    surface = surface_for(box)
    fragments = surface.source_range_fragments(start=0, end=len(word))
    assert fragments
    before = render_surface_viewport(surface)

    surface.set_diagnostics(
        (
            PromptDiagnostic(
                diagnostic_id=f"spelling:0:{len(word)}:{word}",
                kind=PromptDiagnosticKind.SPELLING,
                severity=PromptDiagnosticSeverity.ERROR,
                source_start=0,
                source_end=len(word),
                message=f"Possible spelling issue: {word}",
                payload=PromptSpellingDiagnosticPayload(word=word),
            ),
        )
    )
    process_events(app)
    after = render_surface_viewport(surface)

    centers = _diagnostic_column_centers(before, after, fragments[0])
    assert len(centers) >= 8
    assert max(centers) - min(centers) > 1.0


def test_projection_surface_wildcard_diagnostic_follows_projected_token(
    widgets: list[QWidget],
) -> None:
    """Missing wildcard diagnostics should paint through collapsed token geometry."""

    app = ensure_qapp()
    text = "{missing|2}, suffix"
    box = show_prompt_editor(
        widgets,
        text=text,
        width=360,
    )
    surface = surface_for(box)
    fragments = surface.source_range_fragments(start=0, end=11)
    assert fragments
    before = render_surface_viewport(surface)

    surface.set_diagnostics(
        (
            PromptDiagnostic(
                diagnostic_id="wildcard:0:11:simple:missing:",
                kind=PromptDiagnosticKind.WILDCARD,
                severity=PromptDiagnosticSeverity.ERROR,
                source_start=0,
                source_end=11,
                message="Missing wildcard: missing",
                payload=PromptWildcardDiagnosticPayload(
                    identifier="missing",
                    wildcard_form="simple",
                ),
            ),
        )
    )
    process_events(app)
    after = render_surface_viewport(surface)

    centers = _diagnostic_column_centers(before, after, fragments[0])
    assert len(centers) >= 4
    assert max(centers) - min(centers) > 1.0

    box.setDisplayMode(PromptProjectionDisplayMode.RAW)
    process_events(app)

    raw_fragments = surface.source_range_fragments(start=0, end=11)
    assert raw_fragments


def test_projection_surface_reuses_diagnostic_fragment_geometry(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repeated diagnostic paints should reuse unchanged source-range geometry."""

    word = "missspelledword"
    box = show_prompt_editor(
        widgets,
        text=word,
        width=360,
    )
    surface = surface_for(box)
    diagnostic = PromptDiagnostic(
        diagnostic_id=f"spelling:0:{len(word)}:{word}",
        kind=PromptDiagnosticKind.SPELLING,
        severity=PromptDiagnosticSeverity.ERROR,
        source_start=0,
        source_end=len(word),
        message=f"Possible spelling issue: {word}",
        payload=PromptSpellingDiagnosticPayload(word=word),
    )
    surface.set_diagnostics((diagnostic,))
    layout = cast(Any, surface)._layout
    original_source_range_fragments = layout.source_range_fragments
    fragment_lookup_count = 0

    def count_source_range_fragments(
        start: int,
        end: int,
        *,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[QRectF, ...]:
        nonlocal fragment_lookup_count
        fragment_lookup_count += 1
        return cast(
            tuple[QRectF, ...],
            original_source_range_fragments(
                start=start,
                end=end,
                viewport_rect=viewport_rect,
                scroll_offset=scroll_offset,
            ),
        )

    monkeypatch.setattr(layout, "source_range_fragments", count_source_range_fragments)
    viewport_rect = QRectF(surface.viewport().rect())
    scroll_offset = cast(Any, surface)._scroll_offset()

    first_fragments = cast(Any, surface)._diagnostic_fragments_for_paint(
        diagnostic,
        viewport_rect=viewport_rect,
        scroll_offset=scroll_offset,
    )
    second_fragments = cast(Any, surface)._diagnostic_fragments_for_paint(
        diagnostic,
        viewport_rect=viewport_rect,
        scroll_offset=scroll_offset,
    )

    assert first_fragments
    assert second_fragments == first_fragments
    assert fragment_lookup_count == 1

    replacement = PromptDiagnostic(
        diagnostic_id=f"spelling:0:{len(word)}:{word}:replacement",
        kind=PromptDiagnosticKind.SPELLING,
        severity=PromptDiagnosticSeverity.ERROR,
        source_start=0,
        source_end=len(word),
        message=f"Possible spelling issue: {word}",
        payload=PromptSpellingDiagnosticPayload(word=word),
    )
    surface.set_diagnostics((replacement,))

    assert not cast(Any, surface)._diagnostic_painter.fragment_cache


def test_projection_surface_preserves_diagnostic_fragments_after_hard_line_edit(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hard-line edits before diagnostics should shift cached underline geometry."""

    text = "alpha beta"
    word_start = text.index("beta")
    word_end = word_start + len("beta")
    box = show_prompt_editor(
        widgets,
        text=text,
        width=360,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
    diagnostic = PromptDiagnostic(
        diagnostic_id="spelling:beta",
        kind=PromptDiagnosticKind.SPELLING,
        severity=PromptDiagnosticSeverity.ERROR,
        source_start=word_start,
        source_end=word_end,
        message="Possible spelling issue: beta",
        payload=PromptSpellingDiagnosticPayload(word="beta"),
    )
    surface.set_diagnostics((diagnostic,))
    layout = cast(Any, surface)._layout
    original_source_range_fragments = layout.source_range_fragments
    fragment_lookup_count = 0

    def count_source_range_fragments(
        start: int,
        end: int,
        *,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[QRectF, ...]:
        """Record diagnostic fragment lookups while preserving layout behavior."""

        nonlocal fragment_lookup_count
        fragment_lookup_count += 1
        return cast(
            tuple[QRectF, ...],
            original_source_range_fragments(
                start=start,
                end=end,
                viewport_rect=viewport_rect,
                scroll_offset=scroll_offset,
            ),
        )

    monkeypatch.setattr(layout, "source_range_fragments", count_source_range_fragments)
    viewport_rect = QRectF(surface.viewport().rect())
    scroll_offset = cast(Any, surface)._scroll_offset()
    cached_fragments = cast(Any, surface)._diagnostic_fragments_for_paint(
        diagnostic,
        viewport_rect=viewport_rect,
        scroll_offset=scroll_offset,
    )

    edit_start = text.index(" beta")
    remapped_diagnostic = replace(
        diagnostic,
        source_start=word_start + 1,
        source_end=word_end + 1,
    )
    cast(Any, surface)._session.set_diagnostics((remapped_diagnostic,))
    next_layout_revision = cast(
        int,
        cast(Any, surface)._diagnostic_painter.advance_layout_revision(
            reason="test_hard_line_edit"
        ),
    )
    cast(Any, surface)._preserve_diagnostic_fragment_cache_for_incremental_edit(
        start=edit_start,
        end=edit_start,
        replacement_text="\n",
        next_layout_revision=next_layout_revision,
        fragment_y_delta=20.0,
    )
    remapped_fragments = cast(Any, surface)._diagnostic_fragments_for_paint(
        remapped_diagnostic,
        viewport_rect=viewport_rect,
        scroll_offset=scroll_offset,
    )

    assert fragment_lookup_count == 1
    assert remapped_diagnostic.source_start == word_start + 1
    assert remapped_diagnostic.source_end == word_end + 1
    assert remapped_fragments
    assert remapped_fragments[0].top() > cached_fragments[0].top()
    flush_projection_update_scheduler(surface)


def test_projection_surface_preserves_diagnostic_fragments_after_fast_delete(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fast trailing delete should not force diagnostic underline lookup misses."""

    text = "alpha betaX"
    box = show_prompt_editor(
        widgets,
        text=text,
        width=360,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
    diagnostic = PromptDiagnostic(
        diagnostic_id="spelling:alpha",
        kind=PromptDiagnosticKind.SPELLING,
        severity=PromptDiagnosticSeverity.ERROR,
        source_start=0,
        source_end=len("alpha"),
        message="Possible spelling issue: alpha",
        payload=PromptSpellingDiagnosticPayload(word="alpha"),
    )
    surface.set_diagnostics((diagnostic,))
    layout = cast(Any, surface)._layout
    original_source_range_fragments = layout.source_range_fragments
    fragment_lookup_count = 0

    def count_source_range_fragments(
        start: int,
        end: int,
        *,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[QRectF, ...]:
        """Record diagnostic fragment lookups while preserving layout behavior."""

        nonlocal fragment_lookup_count
        fragment_lookup_count += 1
        return cast(
            tuple[QRectF, ...],
            original_source_range_fragments(
                start=start,
                end=end,
                viewport_rect=viewport_rect,
                scroll_offset=scroll_offset,
            ),
        )

    monkeypatch.setattr(layout, "source_range_fragments", count_source_range_fragments)
    viewport_rect = QRectF(surface.viewport().rect())
    scroll_offset = cast(Any, surface)._scroll_offset()
    first_fragments = cast(Any, surface)._diagnostic_fragments_for_paint(
        diagnostic,
        viewport_rect=viewport_rect,
        scroll_offset=scroll_offset,
    )

    next_text = text[:-1]
    previous_signal_state = surface.blockSignals(True)
    try:
        apply_source_range_to_projection(
            surface,
            next_text,
            cursor_position=len(next_text),
            anchor_position=len(next_text),
            emit_text_changed=False,
            source_edit_start=len(text) - 1,
            source_edit_end=len(text),
            source_edit_replacement_text="",
            previous_source_text=text,
        )
    finally:
        surface.blockSignals(previous_signal_state)
    second_fragments = cast(Any, surface)._diagnostic_fragments_for_paint(
        cast(Any, surface)._session.diagnostics[0],
        viewport_rect=viewport_rect,
        scroll_offset=scroll_offset,
    )

    assert fragment_lookup_count == 1
    assert first_fragments
    assert second_fragments == first_fragments
    flush_projection_update_scheduler(surface)


def test_projection_surface_diagnostics_remap_across_plain_typing(
    widgets: list[QWidget],
) -> None:
    """Visible diagnostic ranges should stay attached to their source words."""

    box = show_prompt_editor(
        widgets,
        text="alpha mispelled omega",
        width=360,
    )
    surface = surface_for(box)
    diagnostic = PromptDiagnostic(
        diagnostic_id="spelling:mispelled",
        kind=PromptDiagnosticKind.SPELLING,
        severity=PromptDiagnosticSeverity.ERROR,
        source_start=6,
        source_end=15,
        message="Spelling",
        payload=PromptSpellingDiagnosticPayload(word="mispelled"),
    )
    surface.set_diagnostics((diagnostic,))

    cast(Any, surface)._source_change_applier._remap_diagnostics_for_source_edit(
        start=0,
        end=0,
        replacement_text="x",
    )

    diagnostics = cast(Any, surface)._session.diagnostics
    assert len(diagnostics) == 1
    assert diagnostics[0].source_start == 7
    assert diagnostics[0].source_end == 16


def test_projection_surface_diagnostics_drop_when_edited_inside_word(
    widgets: list[QWidget],
) -> None:
    """A diagnostic being edited should disappear until diagnostics refresh."""

    box = show_prompt_editor(
        widgets,
        text="alpha mispelled omega",
        width=360,
    )
    surface = surface_for(box)
    diagnostic = PromptDiagnostic(
        diagnostic_id="spelling:mispelled",
        kind=PromptDiagnosticKind.SPELLING,
        severity=PromptDiagnosticSeverity.ERROR,
        source_start=6,
        source_end=15,
        message="Spelling",
        payload=PromptSpellingDiagnosticPayload(word="mispelled"),
    )
    surface.set_diagnostics((diagnostic,))

    cast(Any, surface)._source_change_applier._remap_diagnostics_for_source_edit(
        start=10,
        end=10,
        replacement_text="x",
    )

    assert cast(Any, surface)._session.diagnostics == ()

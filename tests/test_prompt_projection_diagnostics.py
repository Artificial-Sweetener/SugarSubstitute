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

from substitute.application.prompt_editor.diagnostics.models import (
    PromptDiagnostic,
    PromptDiagnosticKind,
    PromptDiagnosticSeverity,
    PromptSpellingDiagnosticPayload,
    PromptWildcardDiagnosticPayload,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptLayoutIdentity,
    PromptLayoutRevision,
    PromptProjectionIdentity,
    PromptProjectionRevision,
    PromptSemanticIdentity,
    PromptSemanticRevision,
    PromptSourceIdentity,
)
from substitute.presentation.editor.prompt_editor.geometry.selection import (
    PromptSelectionGeometry,
)
from substitute.presentation.editor.prompt_editor.projection.diagnostic_layer_assets import (
    PromptDiagnosticLayerAssetPreparer,
)
from substitute.presentation.editor.prompt_editor.projection.diagnostic_layer_preparer import (
    PromptDiagnosticLayerPreparer,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
)
from tests.prompt_projection_surface_test_helpers import (
    apply_source_range_to_projection,
    delay_projection_update_scheduler,
    flush_projection_update_scheduler,
    render_surface_viewport,
)
from tests.prompt_projection_surface_test_helpers import (
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
)
from tests.prompt_projection_test_helpers import (
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "projection surface tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


def _observe_source_range_fragment_lookups(
    monkeypatch: pytest.MonkeyPatch,
) -> list[int]:
    """Count calls at the authoritative selection-geometry owner."""

    lookup_count = [0]
    original = PromptSelectionGeometry.source_range_fragments

    def observed_source_range_fragments(
        selection_geometry: PromptSelectionGeometry,
        start: int,
        end: int,
        *,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[QRectF, ...]:
        """Record one lookup while preserving selection geometry behavior."""

        lookup_count[0] += 1
        return original(
            selection_geometry,
            start,
            end,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )

    monkeypatch.setattr(
        PromptSelectionGeometry,
        "source_range_fragments",
        observed_source_range_fragments,
    )
    return lookup_count


def _diagnostic_fragments(
    surface: object,
    diagnostic: PromptDiagnostic,
    *,
    viewport_rect: QRectF,
    scroll_offset: float,
) -> tuple[QRectF, ...]:
    """Query retained fragments through the authoritative diagnostic owner."""

    prompt_surface = cast(Any, surface)
    layout_identity = prompt_surface._frame_state.current_layout_identity(
        prompt_surface._layout.frame.output
    )
    assert layout_identity is not None
    return cast(
        tuple[QRectF, ...],
        prompt_surface._diagnostic_layer_owner.fragments(
            diagnostic,
            geometry=prompt_surface._layout.frame.geometry,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
            layout_identity=layout_identity,
        ),
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


def test_projection_surface_paint_consumes_published_diagnostic_layer(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Paint must not filter diagnostics, query geometry, or select wave assets."""

    app = ensure_qapp()
    word = "missspelledword"
    box = show_prompt_editor(widgets, text=word, width=360)
    surface = surface_for(box)
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
    owner = cast(Any, surface)._diagnostic_layer_owner
    assert owner.layer.underlines
    assert owner.layer.wave_tile is not None

    def reject_preparation(*args: object, **kwargs: object) -> None:
        """Reject command preparation reached from the paint stack."""

        del args, kwargs
        raise AssertionError("diagnostic preparation ran during paint")

    monkeypatch.setattr(
        PromptDiagnosticLayerPreparer,
        "prepare_visible_cached",
        reject_preparation,
    )
    monkeypatch.setattr(
        PromptDiagnosticLayerAssetPreparer,
        "prepare",
        reject_preparation,
    )

    image = render_surface_viewport(surface)

    assert not image.isNull()


def test_projection_surface_selection_republishes_diagnostic_layer(
    widgets: list[QWidget],
) -> None:
    """Selection changes must hide and restore diagnostics before paint."""

    app = ensure_qapp()
    word = "missspelledword"
    box = show_prompt_editor(widgets, text=word, width=360)
    surface = surface_for(box)
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
    owner = cast(Any, surface)._diagnostic_layer_owner
    assert owner.layer.underlines

    editing_session = cast(Any, surface)._editing_session
    editing_session.set_cursor_positions(
        cursor_position=len(word),
        anchor_position=0,
    )
    owner.refresh(reason="selection_changed")

    assert not owner.layer.underlines

    editing_session.set_cursor_positions(
        cursor_position=len(word),
        anchor_position=len(word),
    )
    owner.refresh(reason="selection_changed")
    process_events(app)

    assert owner.layer.underlines


def test_projection_surface_rejects_superseded_diagnostic_warm_work(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A newer diagnostic revision must cancel queued fragment preparation."""

    app = ensure_qapp()
    source = "alpha bravo charlie delta echo foxtrot golf"
    box = show_prompt_editor(widgets, text=source, width=520)
    surface = surface_for(box)
    ranges = tuple(
        (source.index(word), source.index(word) + len(word)) for word in source.split()
    )
    old_diagnostics = tuple(
        PromptDiagnostic(
            diagnostic_id=f"old:{start}:{end}",
            kind=PromptDiagnosticKind.SPELLING,
            severity=PromptDiagnosticSeverity.ERROR,
            source_start=start,
            source_end=end,
            message="Old diagnostic",
            payload=PromptSpellingDiagnosticPayload(word=source[start:end]),
        )
        for start, end in ranges[:-1]
    )
    latest_start, latest_end = ranges[-1]
    latest_diagnostic = PromptDiagnostic(
        diagnostic_id=f"latest:{latest_start}:{latest_end}",
        kind=PromptDiagnosticKind.SPELLING,
        severity=PromptDiagnosticSeverity.ERROR,
        source_start=latest_start,
        source_end=latest_end,
        message="Latest diagnostic",
        payload=PromptSpellingDiagnosticPayload(
            word=source[latest_start:latest_end],
        ),
    )
    fragment_queries: list[tuple[int, int]] = []
    original_fragments = PromptSelectionGeometry.source_range_fragments

    def record_fragments(
        self: PromptSelectionGeometry,
        start: int,
        end: int,
        *,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[QRectF, ...]:
        """Record the diagnostic revision that reaches geometry preparation."""

        fragment_queries.append((start, end))
        return original_fragments(
            self,
            start,
            end,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )

    monkeypatch.setattr(
        PromptSelectionGeometry,
        "source_range_fragments",
        record_fragments,
    )
    surface.set_diagnostics(old_diagnostics)
    surface.set_diagnostics((latest_diagnostic,))
    process_events(app)

    owner = cast(Any, surface)._diagnostic_layer_owner
    assert fragment_queries == [(latest_start, latest_end)]
    assert owner.layer.underlines


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
    fragment_lookup_count = _observe_source_range_fragment_lookups(monkeypatch)
    viewport_rect = QRectF(surface.viewport().rect())
    scroll_offset = cast(Any, surface)._scroll_offset()

    first_fragments = _diagnostic_fragments(
        surface,
        diagnostic,
        viewport_rect=viewport_rect,
        scroll_offset=scroll_offset,
    )
    second_fragments = _diagnostic_fragments(
        surface,
        diagnostic,
        viewport_rect=viewport_rect,
        scroll_offset=scroll_offset,
    )

    assert first_fragments
    assert second_fragments == first_fragments
    assert fragment_lookup_count == [1]

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
    replacement_fragments = _diagnostic_fragments(
        surface,
        replacement,
        viewport_rect=viewport_rect,
        scroll_offset=scroll_offset,
    )

    assert replacement_fragments
    assert fragment_lookup_count == [2]


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
    fragment_lookup_count = _observe_source_range_fragment_lookups(monkeypatch)
    viewport_rect = QRectF(surface.viewport().rect())
    scroll_offset = cast(Any, surface)._scroll_offset()
    cached_fragments = _diagnostic_fragments(
        surface,
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
    previous_layout_identity = cast(Any, surface)._frame_state.current_layout_identity(
        cast(Any, surface)._layout.frame.output,
    )
    assert previous_layout_identity is not None
    next_layout_identity = _next_layout_identity(
        previous_layout_identity,
        next_source_length=len(text) + 1,
    )
    diagnostic_layer_owner = cast(Any, surface)._diagnostic_layer_owner
    diagnostic_layer_owner.preserve_fragment_cache_for_incremental_edit(
        diagnostics=(remapped_diagnostic,),
        start=edit_start,
        end=edit_start,
        replacement_text="\n",
        previous_layout_identity=previous_layout_identity,
        next_layout_identity=next_layout_identity,
        fragment_y_delta=20.0,
    )
    remapped_fragments = diagnostic_layer_owner.fragments(
        remapped_diagnostic,
        geometry=layout.frame.geometry,
        viewport_rect=viewport_rect,
        scroll_offset=scroll_offset,
        layout_identity=next_layout_identity,
    )

    assert fragment_lookup_count == [1]
    assert remapped_diagnostic.source_start == word_start + 1
    assert remapped_diagnostic.source_end == word_end + 1
    assert remapped_fragments
    assert remapped_fragments[0].top() > cached_fragments[0].top()
    flush_projection_update_scheduler(surface)


def _next_layout_identity(
    previous: PromptLayoutIdentity,
    *,
    next_source_length: int,
) -> PromptLayoutIdentity:
    """Return one exact successor lineage for cache-remap tests."""

    previous_semantic = previous.projection.semantic
    source = PromptSourceIdentity(
        previous_semantic.source.source_revision + 1,
        next_source_length,
    )
    semantic = PromptSemanticIdentity(
        source,
        PromptSemanticRevision(int(previous_semantic.semantic_revision) + 1),
    )
    projection = PromptProjectionIdentity(
        semantic,
        PromptProjectionRevision(int(previous.projection.projection_revision) + 1),
    )
    return PromptLayoutIdentity(
        projection,
        PromptLayoutRevision(int(previous.layout_revision) + 1),
    )


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
    fragment_lookup_count = _observe_source_range_fragment_lookups(monkeypatch)
    viewport_rect = QRectF(surface.viewport().rect())
    scroll_offset = cast(Any, surface)._scroll_offset()
    first_fragments = _diagnostic_fragments(
        surface,
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
            source_edit_start=len(text) - 1,
            source_edit_end=len(text),
            source_edit_replacement_text="",
        )
    finally:
        surface.blockSignals(previous_signal_state)
    second_fragments = _diagnostic_fragments(
        surface,
        cast(Any, surface)._session.diagnostics[0],
        viewport_rect=viewport_rect,
        scroll_offset=scroll_offset,
    )

    assert fragment_lookup_count == [1]
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

    previous_signal_state = surface.blockSignals(True)
    try:
        apply_source_range_to_projection(
            surface,
            f"x{surface.toPlainText()}",
            source_edit_start=0,
            source_edit_end=0,
            source_edit_replacement_text="x",
        )
    finally:
        surface.blockSignals(previous_signal_state)

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

    source_text = surface.toPlainText()
    previous_signal_state = surface.blockSignals(True)
    try:
        apply_source_range_to_projection(
            surface,
            f"{source_text[:10]}x{source_text[10:]}",
            source_edit_start=10,
            source_edit_end=10,
            source_edit_replacement_text="x",
        )
    finally:
        surface.blockSignals(previous_signal_state)

    assert cast(Any, surface)._session.diagnostics == ()

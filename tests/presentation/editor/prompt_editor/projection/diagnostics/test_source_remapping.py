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

"""Contracts for prompt projection diagnostic source remapping."""

from __future__ import annotations


from dataclasses import replace
from typing import Any, cast

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.diagnostics.models import (
    PromptDiagnostic,
    PromptDiagnosticKind,
    PromptDiagnosticSeverity,
    PromptSpellingDiagnosticPayload,
)
from tests.support.prompt_editor.projection_surface_support import (
    apply_source_range_to_projection,
    delay_projection_update_scheduler,
    flush_projection_update_scheduler,
)
from tests.support.prompt_editor.projection_surface_support import (  # noqa: F401
    projection_surface_widgets as _projection_surface_widgets,
)
from tests.support.prompt_editor.projection_engine_support import (
    show_prompt_editor,
    surface_for,
)

from .support import (
    _diagnostic_fragments,
    _next_layout_identity,
    _observe_source_range_fragment_lookups,
)


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

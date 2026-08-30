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

"""Contracts for prompt projection diagnostic cache lifecycle."""

from __future__ import annotations


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
from substitute.presentation.editor.prompt_editor.geometry.selection import (
    PromptSelectionGeometry,
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
    _observe_source_range_fragment_lookups,
    wait_for_diagnostic_layer,
)


def test_projection_surface_rejects_superseded_diagnostic_warm_work(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A newer diagnostic revision must cancel queued fragment preparation."""

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
    wait_for_diagnostic_layer(surface, has_underlines=True)

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

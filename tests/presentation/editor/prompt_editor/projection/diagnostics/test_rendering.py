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

"""Contracts for prompt projection diagnostic rendering."""

from __future__ import annotations


from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.diagnostics.models import (
    PromptDiagnostic,
    PromptDiagnosticKind,
    PromptDiagnosticSeverity,
    PromptSpellingDiagnosticPayload,
    PromptWildcardDiagnosticPayload,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
)
from tests.support.prompt_editor.projection_surface_support import (
    render_surface_viewport,
)
from tests.support.prompt_editor.projection_surface_support import (  # noqa: F401
    projection_surface_widgets as _projection_surface_widgets,
)
from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)

from .support import _diagnostic_column_centers, wait_for_diagnostic_layer


def test_projection_surface_diagnostic_renders_wavy_error_underline(
    widgets: list[QWidget],
) -> None:
    """Prompt diagnostics should render as a wavy semantic-error underline."""

    _ = ensure_qapp()
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
    wait_for_diagnostic_layer(surface, has_underlines=True)
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
    wait_for_diagnostic_layer(surface, has_underlines=True)
    after = render_surface_viewport(surface)

    centers = _diagnostic_column_centers(before, after, fragments[0])
    assert len(centers) >= 4
    assert max(centers) - min(centers) > 1.0

    box.setDisplayMode(PromptProjectionDisplayMode.RAW)
    process_events(app)

    raw_fragments = surface.source_range_fragments(start=0, end=11)
    assert raw_fragments

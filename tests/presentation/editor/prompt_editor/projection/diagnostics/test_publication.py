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

"""Contracts for prompt projection diagnostic layer publication."""

from __future__ import annotations


from typing import Any, cast

import pytest
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.diagnostics.models import (
    PromptDiagnostic,
    PromptDiagnosticKind,
    PromptDiagnosticSeverity,
    PromptSpellingDiagnosticPayload,
)
from substitute.presentation.editor.prompt_editor.projection.diagnostic_layer_assets import (
    PromptDiagnosticLayerAssetPreparer,
)
from substitute.presentation.editor.prompt_editor.projection.diagnostic_layer_preparer import (
    PromptDiagnosticLayerPreparer,
)
from tests.support.prompt_editor.projection_surface_support import (
    render_surface_viewport,
)
from tests.support.prompt_editor.projection_surface_support import (  # noqa: F401
    projection_surface_widgets as _projection_surface_widgets,
)
from tests.support.prompt_editor.projection_engine_support import (
    show_prompt_editor,
    surface_for,
)

from .support import wait_for_diagnostic_layer


def test_projection_surface_paint_consumes_published_diagnostic_layer(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Paint must not filter diagnostics, query geometry, or select wave assets."""

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
    wait_for_diagnostic_layer(surface, has_underlines=True)
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
    wait_for_diagnostic_layer(surface, has_underlines=True)
    owner = cast(Any, surface)._diagnostic_layer_owner
    assert owner.layer.underlines

    editing_session = cast(Any, surface)._editing_session
    editing_session.set_cursor_positions(
        cursor_position=len(word),
        anchor_position=0,
    )
    owner.refresh(reason="selection_changed")

    wait_for_diagnostic_layer(surface, has_underlines=False)

    editing_session.set_cursor_positions(
        cursor_position=len(word),
        anchor_position=len(word),
    )
    owner.refresh(reason="selection_changed")
    wait_for_diagnostic_layer(surface, has_underlines=True)

    assert owner.layer.underlines

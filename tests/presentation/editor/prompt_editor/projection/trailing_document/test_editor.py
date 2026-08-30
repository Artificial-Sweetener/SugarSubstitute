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

"""Verify trailing prompt-projection document edit contracts."""

from __future__ import annotations

from dataclasses import replace

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.projection.builder import (
    PromptProjectionBuilder,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptProjectionSession,
)
from substitute.presentation.editor.prompt_editor.projection.trailing_document_editor import (
    PromptTrailingDocumentEditor,
)
from tests.support.prompt_editor.projection_invariants import (
    validate_prompt_projection_document,
)

_PLAIN_RENDER_PLAN = PromptSyntaxRenderPlan(syntax_spans=(), renderer_views=())


def _document(text: str) -> PromptProjectionDocument:
    """Build a canonical plain projection document."""

    return PromptProjectionBuilder().build_projection(
        PromptDocumentService().build_document_view(text),
        _PLAIN_RENDER_PLAN,
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        session=PromptProjectionSession(),
    )


def _assert_matches_canonical(result: PromptProjectionDocument, text: str) -> None:
    """Require a trailing result to equal canonical visible structure."""

    validate_prompt_projection_document(result)
    canonical = _document(text)
    assert result.source_text == canonical.source_text
    assert result.projection_text == canonical.projection_text
    assert tuple(
        (
            run.kind,
            run.source_start,
            run.source_end,
            run.display_text,
            tuple(run.source_positions),
            run.projection_start,
            run.projection_end,
        )
        for run in result.runs
    ) == tuple(
        (
            run.kind,
            run.source_start,
            run.source_end,
            run.display_text,
            tuple(run.source_positions),
            run.projection_start,
            run.projection_end,
        )
        for run in canonical.runs
    )
    assert tuple(
        (
            stop.projection_position,
            stop.state.source_position,
            stop.state.placement,
        )
        for stop in result.caret_map.stops
    ) == tuple(
        (
            stop.projection_position,
            stop.state.source_position,
            stop.state.placement,
        )
        for stop in canonical.caret_map.stops
    )


def test_trailing_document_editor_plain_insert_matches_canonical() -> None:
    """Plain suffix insertion should preserve canonical mapping and caret stops."""

    result = PromptTrailingDocumentEditor().plain_insert(
        previous_document=_document("alpha"),
        next_text="alphax",
        render_plan=_PLAIN_RENDER_PLAN,
    )

    assert result is not None
    _assert_matches_canonical(result, "alphax")


def test_trailing_document_editor_newline_insert_matches_canonical() -> None:
    """Hard-line suffix insertion should preserve canonical mapping and caret stops."""

    result = PromptTrailingDocumentEditor().newline_insert(
        previous_document=_document("alpha"),
        previous_text="alpha",
        next_text="alpha\n",
        start=5,
        end=5,
        render_plan=_PLAIN_RENDER_PLAN,
    )

    assert result is not None
    _assert_matches_canonical(result, "alpha\n")


def test_trailing_document_editor_plain_delete_matches_canonical() -> None:
    """Plain suffix deletion should preserve canonical mapping and caret stops."""

    result = PromptTrailingDocumentEditor().plain_delete(
        previous_document=_document("alphax"),
        previous_text="alphax",
        next_text="alpha",
        start=5,
        end=6,
    )

    assert result is not None
    _assert_matches_canonical(result, "alpha")


def test_trailing_document_editor_newline_delete_matches_canonical() -> None:
    """Hard-line suffix deletion should preserve canonical mapping and caret stops."""

    result = PromptTrailingDocumentEditor().newline_delete(
        previous_document=_document("alpha\n"),
        previous_text="alpha\n",
        next_text="alpha",
        start=5,
        end=6,
    )

    assert result is not None
    _assert_matches_canonical(result, "alpha")


def test_trailing_document_editor_rejects_projected_token_boundary() -> None:
    """A suffix owned by a projected token must use a canonical strategy."""

    text = "alpha"
    plain_document = _document(text)
    token_owned_run = replace(plain_document.runs[-1], token_id="token-1")
    token_owned_document = replace(
        plain_document,
        runs=tuple(plain_document.runs[:-1]) + (token_owned_run,),
    )
    result = PromptTrailingDocumentEditor().plain_insert(
        previous_document=token_owned_document,
        next_text=f"{text}x",
        render_plan=_PLAIN_RENDER_PLAN,
    )

    assert result is None

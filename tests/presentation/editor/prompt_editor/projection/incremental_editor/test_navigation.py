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

"""Contract tests for speculative prompt projection incremental edits."""

from __future__ import annotations


from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.projection.incremental_edit_contracts import (
    PromptProjectionIncrementalEdit,
)
from substitute.presentation.editor.prompt_editor.projection.plain_text_document_editor import (
    PromptPlainTextDocumentEditor,
)
from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretPlacement,
    PromptProjectionCaretState,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptProjectionSession,
)


from .support import _plain_text_projection_document


def test_incremental_plain_text_insert_preserves_caret_navigation() -> None:
    """Plain insert remaps caret stops without changing navigation semantics."""

    previous_text = "alpha beta"
    next_text = "alpha Xbeta"
    previous_document = _plain_text_projection_document(previous_text)
    editor = PromptPlainTextDocumentEditor()

    result = editor.try_build_plain_text_edit(
        PromptProjectionIncrementalEdit(
            start=6,
            end=6,
            replacement_text="X",
            previous_source_text=previous_text,
            next_source_text=next_text,
        ),
        previous_document=previous_document,
        document_view=PromptDocumentService().build_document_view(next_text),
        render_plan=PromptSyntaxRenderPlan(syntax_spans=(), renderer_views=()),
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        session=PromptProjectionSession(),
        active_span_range=None,
        decoration_accent_ranges=(),
        scene_error_keys=frozenset(),
    )

    assert result is not None
    caret_map = result.projection_document.caret_map
    assert tuple(stop.state.source_position for stop in caret_map.stops) == tuple(
        range(len(next_text) + 1)
    )
    assert tuple(stop.projection_position for stop in caret_map.stops) == tuple(
        range(len(next_text) + 1)
    )
    assert (
        caret_map.next_state(
            PromptProjectionCaretState(
                source_position=6,
                placement=PromptProjectionCaretPlacement.PLAIN_TEXT,
                run_id="run-1",
            )
        ).source_position
        == 7
    )


def test_incremental_plain_text_delete_preserves_caret_navigation() -> None:
    """Plain delete remaps caret stops without changing navigation semantics."""

    previous_text = "alpha Xbeta"
    next_text = "alpha beta"
    previous_document = _plain_text_projection_document(previous_text)
    editor = PromptPlainTextDocumentEditor()

    result = editor.try_build_plain_text_edit(
        PromptProjectionIncrementalEdit(
            start=6,
            end=7,
            replacement_text="",
            previous_source_text=previous_text,
            next_source_text=next_text,
        ),
        previous_document=previous_document,
        document_view=PromptDocumentService().build_document_view(next_text),
        render_plan=PromptSyntaxRenderPlan(syntax_spans=(), renderer_views=()),
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        session=PromptProjectionSession(),
        active_span_range=None,
        decoration_accent_ranges=(),
        scene_error_keys=frozenset(),
    )

    assert result is not None
    caret_map = result.projection_document.caret_map
    assert tuple(stop.state.source_position for stop in caret_map.stops) == tuple(
        range(len(next_text) + 1)
    )
    assert tuple(stop.projection_position for stop in caret_map.stops) == tuple(
        range(len(next_text) + 1)
    )
    assert (
        caret_map.previous_state(
            PromptProjectionCaretState(
                source_position=7,
                placement=PromptProjectionCaretPlacement.PLAIN_TEXT,
                run_id="run-1",
            )
        ).source_position
        == 6
    )

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

"""Verify stale caret recovery across incremental projection edits."""

from __future__ import annotations

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.projection.syntax_models import (
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretPlacement,
    PromptProjectionCaretState,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
)
from substitute.presentation.editor.prompt_editor.projection.incremental_edit_contracts import (
    PromptProjectionIncrementalEdit,
)
from substitute.presentation.editor.prompt_editor.projection.plain_text_document_editor import (
    PromptPlainTextDocumentEditor,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptProjectionSession,
)

from .support import _scene_projection_document


def test_incremental_plain_edit_resolves_a_removed_token_state_by_position() -> None:
    """Treat a token absent from the previous stops as a stale caret state."""

    previous_text = "alpha beta"
    next_text = "alpha xbeta"
    editor = PromptPlainTextDocumentEditor()
    result = editor.try_build_plain_text_edit(
        PromptProjectionIncrementalEdit(
            start=6,
            end=6,
            replacement_text="x",
            previous_source_text=previous_text,
            next_source_text=next_text,
        ),
        previous_document=_scene_projection_document(previous_text),
        document_view=PromptDocumentService().build_document_view(next_text),
        render_plan=PromptSyntaxRenderPlan(syntax_spans=(), renderer_views=()),
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        session=PromptProjectionSession(),
        active_span_range=None,
        decoration_accent_ranges=(),
        scene_error_keys=frozenset(),
    )
    assert result is not None

    resolved = result.projection_document.caret_map.resolve_state(
        PromptProjectionCaretState(
            source_position=6,
            placement=PromptProjectionCaretPlacement.TOKEN_CONTENT,
            token_id="removed-token",
            run_id="removed-run",
            token_slot=0,
        )
    )

    assert resolved.source_position == 6
    assert resolved.token_id is None

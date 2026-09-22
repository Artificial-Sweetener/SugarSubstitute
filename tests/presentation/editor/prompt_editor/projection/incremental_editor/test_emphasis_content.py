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

"""Verify bounded incremental edits inside projected emphasis content."""

from __future__ import annotations

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
)
from substitute.presentation.editor.prompt_editor.projection.builder import (
    PromptProjectionBuilder,
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
from tests.support.prompt_editor.autocomplete_support import prompt_syntax_profile
from tests.support.prompt_editor.projection_engine_support import (
    StaticPromptWildcardCatalogGateway,
)


def test_incremental_emphasis_content_insert_matches_canonical_projection() -> None:
    """Update token content locally without changing its decorated contract."""

    previous_text = "(cat:1.05), suffix"
    edit_start = previous_text.index("at")
    next_text = previous_text[:edit_start] + "X" + previous_text[edit_start:]
    document_service = PromptDocumentService()
    syntax_service = PromptSyntaxService(StaticPromptWildcardCatalogGateway({}))
    syntax_profile = prompt_syntax_profile("emphasis")
    previous_view = document_service.build_document_view(previous_text)
    previous_plan = syntax_service.build_render_plan(previous_view, syntax_profile)
    next_view = document_service.build_document_view(next_text)
    next_plan = syntax_service.build_render_plan(next_view, syntax_profile)
    builder = PromptProjectionBuilder()
    session = PromptProjectionSession()
    previous_projection = builder.build_projection(
        previous_view,
        previous_plan,
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        session=session,
    )

    editor = PromptPlainTextDocumentEditor()
    result = editor.try_build_plain_text_edit(
        PromptProjectionIncrementalEdit(
            start=edit_start,
            end=edit_start,
            replacement_text="X",
            previous_source_text=previous_text,
            next_source_text=next_text,
        ),
        previous_document=previous_projection,
        document_view=next_view,
        render_plan=next_plan,
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        session=session,
        active_span_range=None,
        decoration_accent_ranges=(),
        scene_error_keys=frozenset(),
    )

    assert result is not None, editor.last_rejection_reason
    canonical = builder.build_projection(
        next_view,
        next_plan,
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        session=session,
    )
    incremental = result.projection_document
    assert result.edited_token_id is not None
    assert incremental.source_text == canonical.source_text
    assert incremental.projection_text == canonical.projection_text
    assert tuple(
        (
            run.kind,
            run.source_start,
            run.source_end,
            run.display_text,
            tuple(run.source_positions),
            run.projection_start,
            run.projection_end,
            run.renderer_key,
            run.role,
        )
        for run in incremental.runs
    ) == tuple(
        (
            run.kind,
            run.source_start,
            run.source_end,
            run.display_text,
            tuple(run.source_positions),
            run.projection_start,
            run.projection_end,
            run.renderer_key,
            run.role,
        )
        for run in canonical.runs
    )
    assert tuple(incremental.tokens) == tuple(canonical.tokens)
    assert tuple(
        (
            stop.projection_position,
            stop.state.source_position,
            stop.state.placement,
            stop.state.token_slot,
        )
        for stop in incremental.caret_map.stops
    ) == tuple(
        (
            stop.projection_position,
            stop.state.source_position,
            stop.state.placement,
            stop.state.token_slot,
        )
        for stop in canonical.caret_map.stops
    )

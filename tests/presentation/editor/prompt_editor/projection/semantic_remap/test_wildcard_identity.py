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

"""Verify edited wildcard identity survives optimistic semantic remapping."""

from __future__ import annotations

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.projection.syntax_models import (
    PromptWildcardRendererView,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)
from substitute.presentation.editor.prompt_editor.projection.semantic_remap import (
    PromptProjectionSemanticRemapper,
)
from tests.support.prompt_editor.autocomplete_support import prompt_syntax_profile
from tests.support.prompt_editor.projection_engine_support import (
    StaticPromptWildcardCatalogGateway,
)


def test_semantic_remapper_preserves_edited_wildcard_identity_and_tag() -> None:
    """Retain decorated syntax and tag while the edited name is resolving."""

    previous_text = "{color|2}"
    next_text = "{haircolor|2}"
    document_view = PromptDocumentService().build_document_view(previous_text)
    render_plan = PromptSyntaxService(
        StaticPromptWildcardCatalogGateway({})
    ).build_render_plan(document_view, prompt_syntax_profile("wildcard"))

    result = PromptProjectionSemanticRemapper().optimistic_prompt_state_for_edit(
        current_document_view=document_view,
        current_render_plan=render_plan,
        previous_text=previous_text,
        next_text=next_text,
        start=1,
        end=1,
        replacement_text="hair",
    )

    assert result is not None
    next_document_view, next_render_plan = result
    assert next_document_view.wildcard_spans[0].identifier == "haircolor"
    assert next_document_view.wildcard_spans[0].tag == "2"
    assert next_document_view.syntax_spans[0].end == len(next_text)
    wildcard_renderer = next_render_plan.renderer_view_for_kind("wildcard")
    assert isinstance(wildcard_renderer, PromptWildcardRendererView)
    assert wildcard_renderer.wildcard_spans[0].identifier == "haircolor"
    assert wildcard_renderer.wildcard_spans[0].display_tag == "2"
    assert wildcard_renderer.wildcard_spans[0].can_step_tag is True
    assert wildcard_renderer.wildcard_spans[0].resolution_pending is True

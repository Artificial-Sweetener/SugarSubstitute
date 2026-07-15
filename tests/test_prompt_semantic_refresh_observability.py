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

"""Tests for prompt semantic refresh diagnostic context."""

from __future__ import annotations

from time import perf_counter

from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptSyntaxService,
)
from substitute.presentation.editor.prompt_editor.async_work import (
    PromptAsyncResultIdentity,
    PromptSemanticRefreshRequest,
    semantic_refresh_request_context,
)
from tests.prompt_autocomplete_test_helpers import (
    EmptyPromptWildcardCatalogGateway,
    prompt_syntax_profile,
)


def test_semantic_refresh_context_counts_lora_document_and_render_spans() -> None:
    """Semantic refresh diagnostics should include document and render LoRA counts."""

    text = "<lora:midna:1.00>"
    document_view = PromptDocumentService().build_document_view(text)
    render_plan = PromptSyntaxService(
        EmptyPromptWildcardCatalogGateway()
    ).build_render_plan(document_view, prompt_syntax_profile("lora"))
    request = PromptSemanticRefreshRequest(
        identity=PromptAsyncResultIdentity(
            request_id=3,
            editor_session_id="editor-session",
            source_revision=7,
            source_length=len(text),
            feature_profile_id=("lora",),
            scene_context_id="scene-a",
            cube_context_id="cube-a",
            cancellation_generation=4,
        ),
        reason="unit",
        source_text=text,
        prepared_document_view=document_view,
        prepared_render_plan=render_plan,
        coalesced_count=2,
        queued_at=perf_counter(),
        submitted_at=perf_counter(),
    )

    context = semantic_refresh_request_context(request)

    assert context["request_id"] == 3
    assert context["request_reason"] == "unit"
    assert context["editor_session_id"] == "editor-session"
    assert context["source_revision"] == 7
    assert context["source_length"] == len(text)
    assert context["feature_profile_id"] == ("lora",)
    assert context["scene_context_id"] == "scene-a"
    assert context["cube_context_id"] == "cube-a"
    assert context["cancellation_generation"] == 4
    assert context["pending_document_view_present"] is True
    assert context["pending_render_plan_present"] is True
    assert context["coalesced_count"] == 2
    assert "elapsed_ms" in context
    assert "duration_ms" in context
    assert context["document_lora_span_count"] == 1
    assert context["render_plan_lora_span_count"] == 1

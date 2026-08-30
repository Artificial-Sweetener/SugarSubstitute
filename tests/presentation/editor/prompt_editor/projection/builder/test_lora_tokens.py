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

"""Contracts for prompt projection LoRA token collapse."""

from __future__ import annotations


from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.lora.resolution import (
    PromptLoraResolutionStatus,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)
from substitute.domain.model_metadata import BANNER_THUMBNAIL_ROLE
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionTokenKind,
    PromptProjectionTokenNavigationMode,
)
from substitute.presentation.editor.prompt_editor.projection.builder import (
    _lora_projection_collapse_summary,
    _lora_renderer_view_for_plan,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptProjectionSession,
)

from .support import (
    _CIVITAI_MODEL_PAGE_URL,
    _StaticPromptLoraCatalogService,
    _build_projection,
)
from tests.support.prompt_editor.autocomplete_support import prompt_syntax_profile
from tests.support.prompt_editor.projection_engine_support import (
    StaticPromptWildcardCatalogGateway,
)


def test_projection_builder_emits_projected_runs_for_lora_tokens() -> None:
    """Projected mode should collapse LoRA schedules into graphical chips."""

    projection = _build_projection(r"alpha, <lora:Illustrious\Character\Mineru:0.8>")

    assert [token.kind for token in projection.tokens] == [
        PromptProjectionTokenKind.LORA
    ]
    token = projection.tokens[0]
    assert token.display_text == "Sword stances collection [Pony]"
    assert token.lora_version_text == "Battoujutsu"
    assert token.value_text == "0.8"
    assert token.detail_text == r"Illustrious\Character\Mineru"
    assert token.model_page_url == _CIVITAI_MODEL_PAGE_URL
    assert token.status_text is None
    assert token.thumbnail_variants[0].role == BANNER_THUMBNAIL_ROLE
    assert token.navigation_mode is PromptProjectionTokenNavigationMode.ATOMIC
    assert projection.runs[-1].renderer_key == "lora_chip"
    assert projection.runs[-1].display_text == "Sword stances collection [Pony]"


def test_projection_builder_marks_uncataloged_lora_tokens_as_missing() -> None:
    """Unresolved inline LoRA syntax should stay projected but carry missing state."""

    projection = _build_projection(r"alpha, <lora:Unknown\Thing:0.8>")

    assert [token.kind for token in projection.tokens] == [
        PromptProjectionTokenKind.LORA
    ]
    token = projection.tokens[0]
    assert token.exists is False
    assert token.lora_status is PromptLoraResolutionStatus.MISSING
    assert token.status_text == "Not found"
    assert token.display_text == "Thing"
    assert token.detail_text == r"Unknown\Thing"
    assert token.lora_backend_value is None
    assert token.thumbnail_variants == ()


def test_projection_builder_skips_expanded_lora_tokens() -> None:
    """Expanded LoRA tokens should remain raw source instead of collapsing to chips."""

    text = r"alpha, <lora:Illustrious\Character\Mineru:0.8>"
    expanded_range = (7, len(text))
    projection = _build_projection(
        text,
        session=PromptProjectionSession(expanded_source_range=expanded_range),
    )

    assert [
        token.kind
        for token in projection.tokens
        if token.kind is PromptProjectionTokenKind.LORA
    ] == []
    assert projection.projection_text == text


def test_lora_projection_collapse_summary_counts_expanded_skips() -> None:
    """LoRA projection summary should expose expanded-token skip counts."""

    text = r"alpha, <lora:Illustrious\Character\Mineru:0.8>"
    document_service = PromptDocumentService()
    syntax_service = PromptSyntaxService(
        StaticPromptWildcardCatalogGateway({}),
        prompt_lora_catalog_service=_StaticPromptLoraCatalogService(),
    )
    document_view = document_service.build_document_view(text)
    render_plan = syntax_service.build_render_plan(
        document_view,
        prompt_syntax_profile("lora"),
    )
    lora_view = _lora_renderer_view_for_plan(render_plan)
    expanded_range = (7, len(text))

    summary = _lora_projection_collapse_summary(
        document_view=document_view,
        render_plan=render_plan,
        all_supported_ranges=tuple(
            (span.start, span.end) for span in render_plan.syntax_spans
        ),
        lora_view=lora_view,
        lora_candidate_count=0,
        lora_skipped_expanded_count=1,
        lora_skipped_nested_count=0,
        expanded_source_range=expanded_range,
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        candidates=(),
    )

    assert summary.renderer_lora_span_count == 1
    assert summary.lora_candidate_count == 0
    assert summary.lora_skipped_expanded_count == 1
    assert summary.lora_skipped_nested_count == 0
    assert summary.expanded_source_start == expanded_range[0]
    assert summary.expanded_source_end == expanded_range[1]
    assert summary.display_mode == "projected"
    assert summary.projected_lora_chip_count == 0

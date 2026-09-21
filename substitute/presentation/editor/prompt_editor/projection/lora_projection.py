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

"""Project LoRA renderer spans into observable semantic tokens."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sugarsubstitute_shared.localization import ApplicationText, app_text

from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.lora.diagnostics import (
    lora_prompt_context,
    lora_source_range_context,
)
from substitute.application.prompt_editor.projection.syntax_models import (
    PromptLoraRendererSpanView,
    PromptLoraRendererView,
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionThumbnailVariant,
    PromptProjectionToken,
    PromptProjectionTokenKind,
    PromptProjectionTokenNavigationMode,
)
from substitute.presentation.editor.prompt_editor.projection.collapse_models import (
    PromptProjectionCollapseCandidate,
    contains_nested_supported_range,
)
from substitute.presentation.editor.prompt_editor.projection.exact_weight_projection import (
    PromptExactWeightEditProjection,
    exact_weight_edit_for_token,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptProjectionSession,
)
from substitute.shared.logging.logger import get_logger, log_debug

_LORA_KIND = "lora"
_LOGGER = get_logger("presentation.editor.prompt_editor.projection_builder")


@dataclass(frozen=True, slots=True)
class PromptLoraProjectionCollapseSummary:
    """Summarize LoRA collapse decisions for one projection build."""

    source_text_length: int
    render_plan_syntax_count: int
    all_supported_range_count: int
    renderer_lora_span_count: int
    lora_candidate_count: int
    lora_skipped_expanded_count: int
    lora_skipped_nested_count: int
    expanded_source_start: int | None
    expanded_source_end: int | None
    display_mode: str
    projected_lora_chip_count: int


def build_lora_collapse_candidates(
    document_view: PromptDocumentView,
    render_plan: PromptSyntaxRenderPlan,
    *,
    display_mode: PromptProjectionDisplayMode,
    session: PromptProjectionSession,
    active_span_range: tuple[int, int] | None,
    all_supported_ranges: tuple[tuple[int, int], ...],
) -> tuple[PromptProjectionCollapseCandidate, ...]:
    """Return LoRA tokens and emit aggregate collapse diagnostics."""

    lora_view = lora_renderer_view_for_plan(render_plan)
    candidates: list[PromptProjectionCollapseCandidate] = []
    skipped_expanded_count = 0
    skipped_nested_count = 0
    for index, span in enumerate(lora_view.lora_spans):
        token_range = (span.outer_start, span.outer_end)
        if session.expanded_source_range == token_range:
            skipped_expanded_count += 1
            _log_lora_projection_skip(
                span,
                skip_reason="expanded_token",
                expanded_source_range=session.expanded_source_range,
            )
            continue
        if contains_nested_supported_range(token_range, all_supported_ranges):
            skipped_nested_count += 1
            _log_lora_projection_skip(
                span,
                skip_reason="nested_supported_range",
                expanded_source_range=session.expanded_source_range,
            )
            continue
        token_id = f"lora:{index}:{span.outer_start}"
        candidates.append(
            PromptProjectionCollapseCandidate(
                start=span.outer_start,
                end=span.outer_end,
                token=_lora_projection_token(
                    span,
                    token_id=token_id,
                    active=active_span_range == token_range,
                    exact_weight_edit=exact_weight_edit_for_token(
                        session,
                        token_id=token_id,
                        content_start=span.name_start,
                        content_end=span.name_end,
                    ),
                ),
            )
        )
    if lora_view.lora_spans:
        _log_lora_projection_collapse_summary(
            lora_projection_collapse_summary(
                document_view=document_view,
                render_plan=render_plan,
                all_supported_ranges=all_supported_ranges,
                lora_view=lora_view,
                lora_candidate_count=len(candidates),
                lora_skipped_expanded_count=skipped_expanded_count,
                lora_skipped_nested_count=skipped_nested_count,
                expanded_source_range=session.expanded_source_range,
                display_mode=display_mode,
                candidates=tuple(candidates),
            )
        )
    return tuple(candidates)


def lora_renderer_view_for_plan(
    render_plan: PromptSyntaxRenderPlan,
) -> PromptLoraRendererView:
    """Return the typed LoRA view registered in one render plan."""

    renderer_view = render_plan.renderer_view_for_kind(_LORA_KIND)
    if isinstance(renderer_view, PromptLoraRendererView):
        return renderer_view
    return PromptLoraRendererView(
        kind=_LORA_KIND,
        syntax_spans=(),
        lora_spans=(),
    )


def lora_projection_collapse_summary(
    *,
    document_view: PromptDocumentView,
    render_plan: PromptSyntaxRenderPlan,
    all_supported_ranges: tuple[tuple[int, int], ...],
    lora_view: PromptLoraRendererView,
    lora_candidate_count: int,
    lora_skipped_expanded_count: int,
    lora_skipped_nested_count: int,
    expanded_source_range: tuple[int, int] | None,
    display_mode: PromptProjectionDisplayMode,
    candidates: tuple[PromptProjectionCollapseCandidate, ...],
) -> PromptLoraProjectionCollapseSummary:
    """Return aggregate LoRA collapse diagnostics for tests and logging."""

    return PromptLoraProjectionCollapseSummary(
        source_text_length=len(document_view.source_text),
        render_plan_syntax_count=len(render_plan.syntax_spans),
        all_supported_range_count=len(all_supported_ranges),
        renderer_lora_span_count=len(lora_view.lora_spans),
        lora_candidate_count=lora_candidate_count,
        lora_skipped_expanded_count=lora_skipped_expanded_count,
        lora_skipped_nested_count=lora_skipped_nested_count,
        expanded_source_start=(
            None if expanded_source_range is None else expanded_source_range[0]
        ),
        expanded_source_end=(
            None if expanded_source_range is None else expanded_source_range[1]
        ),
        display_mode=display_mode.value,
        projected_lora_chip_count=sum(
            1
            for candidate in candidates
            if candidate.token.kind is PromptProjectionTokenKind.LORA
        ),
    )


def _log_lora_projection_collapse_summary(
    summary: PromptLoraProjectionCollapseSummary,
) -> None:
    """Emit one aggregate LoRA projection-collapse diagnostic event."""

    log_debug(
        _LOGGER,
        "prompt_lora_projection.collapse_summary",
        source_text_length=summary.source_text_length,
        render_plan_syntax_count=summary.render_plan_syntax_count,
        all_supported_range_count=summary.all_supported_range_count,
        renderer_lora_span_count=summary.renderer_lora_span_count,
        lora_candidate_count=summary.lora_candidate_count,
        lora_skipped_expanded_count=summary.lora_skipped_expanded_count,
        lora_skipped_nested_count=summary.lora_skipped_nested_count,
        expanded_source_start=summary.expanded_source_start,
        expanded_source_end=summary.expanded_source_end,
        display_mode=summary.display_mode,
        projected_lora_chip_count=summary.projected_lora_chip_count,
    )


def _log_lora_projection_skip(
    span: PromptLoraRendererSpanView,
    *,
    skip_reason: str,
    expanded_source_range: tuple[int, int] | None,
) -> None:
    """Emit one diagnostic event for a skipped LoRA candidate."""

    if not _LOGGER.isEnabledFor(logging.DEBUG):
        return
    log_debug(
        _LOGGER,
        "prompt_lora_projection.skip",
        **lora_prompt_context(span.prompt_name),
        **lora_source_range_context(span.outer_start, span.outer_end),
        skip_reason=skip_reason,
        expanded_source_start=(
            None if expanded_source_range is None else expanded_source_range[0]
        ),
        expanded_source_end=(
            None if expanded_source_range is None else expanded_source_range[1]
        ),
    )


def _lora_projection_token(
    span: PromptLoraRendererSpanView,
    *,
    token_id: str,
    active: bool,
    exact_weight_edit: PromptExactWeightEditProjection | None,
) -> PromptProjectionToken:
    """Build one renderer-ready LoRA token."""

    return PromptProjectionToken(
        token_id=token_id,
        kind=PromptProjectionTokenKind.LORA,
        source_start=span.outer_start,
        source_end=span.outer_end,
        display_text=span.display_name,
        value_text=span.first_weight_text,
        status_text=_lora_status_text(span),
        detail_text=span.prompt_name,
        lora_status=span.lora_status,
        lora_status_reason=span.status_reason,
        lora_match_source=span.match_source,
        lora_authority=span.authority,
        lora_backend_value=span.backend_value,
        lora_version_text=span.display_subtitle,
        lora_trained_words=span.trained_words,
        model_page_url=span.model_page_url,
        thumbnail_variants=tuple(
            PromptProjectionThumbnailVariant(
                size=variant.size,
                storage_key=variant.storage_key,
                width=variant.width,
                height=variant.height,
                content_format=variant.content_format,
                byte_size=variant.byte_size,
                role=variant.role,
            )
            for variant in span.thumbnail_variants
        ),
        exists=span.exists,
        active=active,
        content_start=span.name_start,
        content_end=span.name_end,
        editing_value_text=(
            None if exact_weight_edit is None else exact_weight_edit.value_text
        ),
        editing_slot_width=(
            None if exact_weight_edit is None else exact_weight_edit.slot_width
        ),
        editing_caret_index=(
            None if exact_weight_edit is None else exact_weight_edit.caret_index
        ),
        editing_select_all=(
            False if exact_weight_edit is None else exact_weight_edit.select_all
        ),
        navigation_mode=PromptProjectionTokenNavigationMode.ATOMIC,
    )


def _lora_status_text(span: PromptLoraRendererSpanView) -> ApplicationText | None:
    """Return compact status text for a projected LoRA chip."""

    if span.lora_status.value == "missing":
        return app_text("Not found")
    if span.lora_status.value == "ambiguous":
        return app_text("Ambiguous")
    return None


__all__ = [
    "PromptLoraProjectionCollapseSummary",
    "build_lora_collapse_candidates",
    "lora_projection_collapse_summary",
    "lora_renderer_view_for_plan",
]

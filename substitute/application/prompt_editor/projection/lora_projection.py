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

"""Resolve parsed LoRA spans into renderer-facing projections."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from substitute.application.prompt_editor.document.views import (
    PromptDocumentView,
    PromptLoraView,
    PromptSyntaxSpanView,
)
from substitute.application.prompt_editor.features.syntax_profile import (
    PromptSyntaxProfile,
)
from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogLookup,
)
from substitute.application.prompt_editor.lora.diagnostics import lora_prompt_context
from substitute.application.prompt_editor.lora.resolution import (
    PromptLoraResolution,
    PromptLoraResolutionService,
    PromptLoraResolutionStatus,
)
from substitute.application.prompt_editor.projection.syntax_models import (
    PromptLoraRendererSpanView,
)
from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger("application.prompt_editor.projection.lora_projection")


@dataclass(frozen=True, slots=True)
class PromptLoraRenderPlanSummary:
    """Summarize LoRA renderer metadata for one syntax render plan."""

    source_text_length: int
    syntax_profile: str
    document_lora_span_count: int
    active_lora_syntax_span_count: int
    renderer_lora_span_count: int
    resolved_lora_count: int
    missing_lora_count: int
    non_authoritative_unresolved_count: int
    cache_revision: str


class PromptLoraRendererProjector:
    """Project LoRA spans with catalog metadata and resolution diagnostics."""

    def __init__(self, catalog: PromptLoraCatalogLookup | None) -> None:
        """Store the optional catalog and its resolution policy."""

        self._catalog = catalog
        self._resolution_service = PromptLoraResolutionService(catalog)

    def project(
        self,
        lora_spans: tuple[PromptLoraView, ...],
    ) -> tuple[PromptLoraRendererSpanView, ...]:
        """Return renderer-ready LoRA spans in source order."""

        return tuple(
            _renderer_span(
                lora_span,
                self._resolve(lora_span.prompt_name),
            )
            for lora_span in lora_spans
        )

    def log_render_plan_summary(
        self,
        *,
        document_view: PromptDocumentView,
        syntax_profile: PromptSyntaxProfile,
        active_lora_syntax_spans: tuple[PromptSyntaxSpanView, ...],
        lora_renderer_spans: tuple[PromptLoraRendererSpanView, ...],
        cache_revision: str,
    ) -> None:
        """Publish aggregate LoRA resolution state for one render plan."""

        _log_render_plan_summary(
            summarize_lora_render_plan(
                document_view=document_view,
                syntax_profile=syntax_profile,
                active_lora_syntax_spans=active_lora_syntax_spans,
                lora_renderer_spans=lora_renderer_spans,
                cache_revision=cache_revision,
            )
        )

    def _resolve(self, prompt_name: str) -> PromptLoraResolution:
        """Return catalog metadata and absence authority for one LoRA name."""

        if self._catalog is None:
            resolution = self._resolution_service.resolve(prompt_name)
            _log_resolution_result(
                prompt_name,
                resolution=resolution,
                catalog_available=False,
                catalog_lookup_succeeded=False,
            )
            return resolution
        try:
            resolution = self._resolution_service.resolve(prompt_name)
            _log_resolution_result(
                prompt_name,
                resolution=resolution,
                catalog_available=True,
                catalog_lookup_succeeded=True,
            )
            return resolution
        except Exception:
            resolution = PromptLoraResolution(
                status=PromptLoraResolutionStatus.CATALOG_UNAVAILABLE,
                catalog_item=None,
                authority=False,
                match_source="catalog_exception",
                status_reason="catalog_lookup_failed",
            )
            _log_resolution_result(
                prompt_name,
                resolution=resolution,
                catalog_available=True,
                catalog_lookup_succeeded=False,
            )
            _LOGGER.warning(
                "LoRA catalog lookup failed; using fallback renderer span"
                " | prompt_name=%s",
                prompt_name,
                exc_info=True,
            )
            return resolution


def _renderer_span(
    lora_span: PromptLoraView,
    resolution: PromptLoraResolution,
) -> PromptLoraRendererSpanView:
    """Combine one parsed LoRA span with optional catalog metadata."""

    catalog_item = resolution.catalog_item
    display_name = (
        _fallback_display_name(lora_span.prompt_name)
        if catalog_item is None
        else catalog_item.display_name or catalog_item.basename
    )
    thumbnail_variants = () if catalog_item is None else catalog_item.thumbnail_variants
    return PromptLoraRendererSpanView(
        outer_start=lora_span.outer_start,
        outer_end=lora_span.outer_end,
        name_start=lora_span.name_start,
        name_end=lora_span.name_end,
        first_weight_start=lora_span.first_weight_start,
        first_weight_end=lora_span.first_weight_end,
        first_weight=lora_span.first_weight,
        first_weight_text=lora_span.first_weight_text,
        second_weight_start=lora_span.second_weight_start,
        second_weight_end=lora_span.second_weight_end,
        second_weight=lora_span.second_weight,
        second_weight_text=lora_span.second_weight_text,
        prompt_name=lora_span.prompt_name,
        backend_value=None if catalog_item is None else catalog_item.backend_value,
        display_name=display_name,
        display_subtitle=None
        if catalog_item is None
        else catalog_item.display_subtitle,
        trained_words=() if catalog_item is None else catalog_item.trained_words,
        thumbnail_variants=thumbnail_variants,
        model_page_url=None if catalog_item is None else catalog_item.model_page_url,
        folder="" if catalog_item is None else catalog_item.folder,
        base_model=None if catalog_item is None else catalog_item.base_model,
        has_collision=False if catalog_item is None else catalog_item.has_collision,
        lora_status=resolution.status,
        match_source=resolution.match_source,
        status_reason=resolution.status_reason,
        authority=resolution.authority,
        ambiguity_candidate_count=resolution.ambiguity_candidate_count,
        exists=not resolution.is_error,
        depth=lora_span.depth,
    )


def _fallback_display_name(prompt_name: str) -> str:
    """Return a basename-derived display name for uncataloged LoRA syntax."""

    normalized_prompt_name = prompt_name.replace("\\", "/")
    return normalized_prompt_name.rsplit("/", maxsplit=1)[-1] or prompt_name


def _log_resolution_result(
    prompt_name: str,
    *,
    resolution: PromptLoraResolution,
    catalog_available: bool,
    catalog_lookup_succeeded: bool,
) -> None:
    """Emit one structured LoRA catalog-resolution event."""

    if not _LOGGER.isEnabledFor(logging.DEBUG):
        return
    catalog_item = resolution.catalog_item
    log_debug(
        _LOGGER,
        "prompt_lora_resolution.result",
        **lora_prompt_context(prompt_name),
        catalog_available=catalog_available,
        catalog_lookup_succeeded=catalog_lookup_succeeded,
        catalog_item_found=catalog_item is not None,
        authority=resolution.authority,
        resolution_status=resolution.status.value,
        match_source=resolution.match_source,
        status_reason=resolution.status_reason,
        ambiguity_candidate_count=resolution.ambiguity_candidate_count,
        will_render_exists=not resolution.is_error,
        display_name_source="catalog" if catalog_item is not None else "fallback",
    )


def summarize_lora_render_plan(
    *,
    document_view: PromptDocumentView,
    syntax_profile: PromptSyntaxProfile,
    active_lora_syntax_spans: tuple[PromptSyntaxSpanView, ...],
    lora_renderer_spans: tuple[PromptLoraRendererSpanView, ...],
    cache_revision: str,
) -> PromptLoraRenderPlanSummary:
    """Return aggregate LoRA render metadata for observability."""

    resolved_lora_count = sum(
        1
        for span in lora_renderer_spans
        if span.lora_status is PromptLoraResolutionStatus.FOUND
    )
    missing_lora_count = sum(
        1
        for span in lora_renderer_spans
        if span.lora_status
        in {
            PromptLoraResolutionStatus.MISSING,
            PromptLoraResolutionStatus.AMBIGUOUS,
        }
    )
    non_authoritative_unresolved_count = sum(
        1
        for span in lora_renderer_spans
        if span.lora_status
        in {
            PromptLoraResolutionStatus.PENDING_NO_AUTHORITY,
            PromptLoraResolutionStatus.CATALOG_UNAVAILABLE,
        }
    )
    return PromptLoraRenderPlanSummary(
        source_text_length=len(document_view.source_text),
        syntax_profile=",".join(syntax_profile.enabled_syntaxes),
        document_lora_span_count=len(document_view.lora_spans),
        active_lora_syntax_span_count=len(active_lora_syntax_spans),
        renderer_lora_span_count=len(lora_renderer_spans),
        resolved_lora_count=resolved_lora_count,
        missing_lora_count=missing_lora_count,
        non_authoritative_unresolved_count=non_authoritative_unresolved_count,
        cache_revision=cache_revision,
    )


def _log_render_plan_summary(summary: PromptLoraRenderPlanSummary) -> None:
    """Emit one aggregate LoRA render-plan diagnostic event."""

    log_debug(
        _LOGGER,
        "prompt_lora_render_plan.summary",
        source_text_length=summary.source_text_length,
        syntax_profile=summary.syntax_profile,
        document_lora_span_count=summary.document_lora_span_count,
        active_lora_syntax_span_count=summary.active_lora_syntax_span_count,
        renderer_lora_span_count=summary.renderer_lora_span_count,
        resolved_lora_count=summary.resolved_lora_count,
        missing_lora_count=summary.missing_lora_count,
        non_authoritative_unresolved_count=summary.non_authoritative_unresolved_count,
        cache_revision=summary.cache_revision,
    )


__all__ = [
    "PromptLoraRendererProjector",
    "PromptLoraRenderPlanSummary",
    "summarize_lora_render_plan",
]

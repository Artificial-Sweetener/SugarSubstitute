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

"""Project renderer-ready syntax state from an existing application document view."""

from __future__ import annotations

import logging
from collections import Counter, OrderedDict
from collections.abc import Hashable
from dataclasses import dataclass
from decimal import Decimal
import hashlib
import re
from threading import RLock
from time import perf_counter

from substitute.application.ports import (
    PromptWildcardCatalogGateway,
    PromptWildcardReference,
    PromptWildcardResolution,
)

from .prompt_document_views import (
    PromptDocumentView,
    PromptEmphasisView,
    PromptLoraView,
    PromptSyntaxSpanView,
    PromptWildcardView,
)
from .prompt_document_semantics import (
    OrdinaryPromptDocumentSemantics,
    PromptDocumentSemantics,
    PromptValueMapping,
)
from .prompt_document_projector import PromptDocumentProjector
from .prompt_structured_syntax_projector import PromptStructuredSyntaxProjector
from .prompt_lora_catalog_service import (
    PromptLoraCatalogLookup,
    PromptLoraThumbnailVariant,
)
from .prompt_lora_diagnostics import lora_prompt_context
from .prompt_lora_resolution_service import (
    PromptLoraResolution,
    PromptLoraResolutionService,
    PromptLoraResolutionStatus,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_timing,
)

from .prompt_syntax_profile_service import PromptSyntaxProfile

_EMPHASIS_KIND = "emphasis"

_LORA_KIND = "lora"
_WILDCARD_KIND = "wildcard"
_NUMERIC_WILDCARD_TAG_PATTERN = re.compile(r"^[1-9][0-9]*$")
_PROMPT_SCENE_PARSING_VERSION = "prompt-scene-v1"
_RENDER_PLAN_CACHE_LIMIT = 512
_RENDER_PLAN_CACHE: OrderedDict[
    "PromptProjectionInputCacheKey",
    "PromptSyntaxRenderPlan",
] = OrderedDict()
_RENDER_PLAN_CACHE_LOCK = RLock()
_LOGGER = get_logger("application.prompt_editor.prompt_syntax_service")


@dataclass(frozen=True, slots=True)
class PromptProjectionInputCacheKey:
    """Identify pure prompt projection inputs independent of widget geometry."""

    source_text_hash: str
    source_text_length: int
    syntax_profile_identity: tuple[str, ...]
    feature_profile_identity: tuple[str, ...]
    wildcard_catalog_revision: str
    lora_model_metadata_revision: str
    scene_parsing_version: str
    document_semantics_identity: Hashable


@dataclass(frozen=True, slots=True)
class PromptSyntaxRendererView:
    """Describe one renderer-facing syntax projection keyed by syntax kind."""

    kind: str
    syntax_spans: tuple[PromptSyntaxSpanView, ...]


@dataclass(frozen=True, slots=True)
class PromptEmphasisRendererView(PromptSyntaxRendererView):
    """Describe the renderer-ready emphasis projection for one prompt snapshot."""

    emphasis_spans: tuple[PromptEmphasisView, ...]


@dataclass(frozen=True, slots=True)
class PromptWildcardRendererSpanView:
    """Describe one renderer-ready wildcard placeholder with resolution state."""

    outer_start: int
    outer_end: int
    content_start: int
    content_end: int
    wildcard_form: str
    identifier: str
    csv_column: str | None
    tag: str | None
    exists: bool
    matched_csv_column: str | None
    available_csv_columns: tuple[str, ...]
    depth: int
    source_key: str
    display_text: str
    display_tag: str | None
    tag_is_explicit: bool
    tag_is_numeric: bool
    can_step_tag: bool
    source_occurrence_count: int


@dataclass(frozen=True, slots=True)
class PromptWildcardRendererView(PromptSyntaxRendererView):
    """Describe the renderer-ready wildcard projection for one prompt snapshot."""

    wildcard_spans: tuple[PromptWildcardRendererSpanView, ...]


@dataclass(frozen=True, slots=True)
class PromptLoraRendererSpanView:
    """Describe one renderer-ready LoRA schedule with catalog metadata."""

    outer_start: int
    outer_end: int
    name_start: int
    name_end: int
    first_weight_start: int
    first_weight_end: int
    first_weight: Decimal
    first_weight_text: str
    second_weight_start: int | None
    second_weight_end: int | None
    second_weight: Decimal | None
    second_weight_text: str | None
    prompt_name: str
    backend_value: str | None
    display_name: str
    display_subtitle: str | None
    trained_words: tuple[str, ...]
    thumbnail_variants: tuple[PromptLoraThumbnailVariant, ...]
    model_page_url: str | None
    folder: str
    base_model: str | None
    has_collision: bool
    lora_status: PromptLoraResolutionStatus
    match_source: str
    status_reason: str
    authority: bool
    ambiguity_candidate_count: int
    exists: bool
    depth: int


@dataclass(frozen=True, slots=True)
class PromptLoraRendererView(PromptSyntaxRendererView):
    """Describe the renderer-ready LoRA projection for one prompt snapshot."""

    lora_spans: tuple[PromptLoraRendererSpanView, ...]


@dataclass(frozen=True, slots=True)
class _PromptLoraRenderPlanSummary:
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


@dataclass(frozen=True, slots=True)
class PromptSyntaxRenderPlan:
    """Group all renderer-facing syntax projections for one prompt snapshot."""

    syntax_spans: tuple[PromptSyntaxSpanView, ...]
    renderer_views: tuple[PromptSyntaxRendererView, ...]
    document_semantics_identity: Hashable = "ordinary-prompt-v1"

    def renderer_view_for_kind(self, kind: str) -> PromptSyntaxRendererView | None:
        """Return the renderer view registered for one syntax kind."""

        for renderer_view in self.renderer_views:
            if renderer_view.kind == kind:
                return renderer_view
        return None


class PromptSyntaxService:
    """Build application-owned syntax projections for presentation renderers."""

    def __init__(
        self,
        prompt_wildcard_catalog_gateway: PromptWildcardCatalogGateway,
        prompt_lora_catalog_service: PromptLoraCatalogLookup | None = None,
        document_semantics: PromptDocumentSemantics | None = None,
    ) -> None:
        """Store syntax metadata collaborators used for renderer resolution state."""

        self._prompt_wildcard_catalog_gateway = prompt_wildcard_catalog_gateway
        self._prompt_lora_catalog_service = prompt_lora_catalog_service
        self._document_semantics = (
            document_semantics or OrdinaryPromptDocumentSemantics()
        )
        self._structured_syntax_projector = PromptStructuredSyntaxProjector(
            document_projector=PromptDocumentProjector(),
            document_semantics=self._document_semantics,
        )
        self._prompt_lora_resolution_service = PromptLoraResolutionService(
            prompt_lora_catalog_service
        )

    def build_render_plan(
        self,
        document_view: PromptDocumentView,
        syntax_profile: PromptSyntaxProfile,
    ) -> PromptSyntaxRenderPlan:
        """Build the complete syntax render plan from one existing document view."""

        cache_key = _render_plan_cache_key(
            document_view,
            syntax_profile,
            wildcard_catalog=self._prompt_wildcard_catalog_gateway,
            lora_catalog=self._prompt_lora_catalog_service,
            document_semantics=self._document_semantics,
        )
        with _RENDER_PLAN_CACHE_LOCK:
            cached = _RENDER_PLAN_CACHE.get(cache_key)
            if cached is not None:
                _RENDER_PLAN_CACHE.move_to_end(cache_key)
                cache_size = len(_RENDER_PLAN_CACHE)
            else:
                cache_size = len(_RENDER_PLAN_CACHE)
        if cached is not None:
            log_debug(
                _LOGGER,
                "Prompt syntax render plan cache hit",
                text_length=cache_key.source_text_length,
                syntax_profile=",".join(cache_key.syntax_profile_identity),
                wildcard_revision=cache_key.wildcard_catalog_revision,
                lora_revision=cache_key.lora_model_metadata_revision,
                cache_size=cache_size,
            )
            return cached

        started_at = perf_counter()
        render_plan = self._build_uncached_render_plan(document_view, syntax_profile)
        with _RENDER_PLAN_CACHE_LOCK:
            cached = _RENDER_PLAN_CACHE.get(cache_key)
            if cached is not None:
                _RENDER_PLAN_CACHE.move_to_end(cache_key)
                cache_size = len(_RENDER_PLAN_CACHE)
                render_plan = cached
            else:
                _RENDER_PLAN_CACHE[cache_key] = render_plan
                _RENDER_PLAN_CACHE.move_to_end(cache_key)
                while len(_RENDER_PLAN_CACHE) > _RENDER_PLAN_CACHE_LIMIT:
                    _RENDER_PLAN_CACHE.popitem(last=False)
                cache_size = len(_RENDER_PLAN_CACHE)
        log_timing(
            _LOGGER,
            "Prompt syntax render plan cache miss",
            started_at=started_at,
            level="debug",
            text_length=cache_key.source_text_length,
            syntax_profile=",".join(cache_key.syntax_profile_identity),
            wildcard_revision=cache_key.wildcard_catalog_revision,
            lora_revision=cache_key.lora_model_metadata_revision,
            cache_size=cache_size,
        )
        return render_plan

    def invalidate_cache(self) -> None:
        """Clear shared pure syntax render-plan cache entries."""

        clear_prompt_syntax_render_plan_cache()

    def _build_uncached_render_plan(
        self,
        document_view: PromptDocumentView,
        syntax_profile: PromptSyntaxProfile,
    ) -> PromptSyntaxRenderPlan:
        """Build the syntax render plan without consulting the shared cache."""

        value_mappings = (
            self._document_semantics.value_mappings_for_text(document_view.source_text)
            if self._document_semantics.uses_structured_prompt_values
            else OrdinaryPromptDocumentSemantics().value_mappings_for_text(
                document_view.source_text
            )
        )
        document_view = self._structured_syntax_projector.project(document_view)
        active_syntax_spans = tuple(
            span
            for span in document_view.syntax_spans
            if syntax_profile.supports(span.kind)
            and _range_belongs_to_value(span.start, span.end, value_mappings)
        )
        renderer_views: list[PromptSyntaxRendererView] = []

        if syntax_profile.supports(_EMPHASIS_KIND):
            emphasis_syntax_spans = tuple(
                span for span in active_syntax_spans if span.kind == _EMPHASIS_KIND
            )
            renderer_views.append(
                PromptEmphasisRendererView(
                    kind=_EMPHASIS_KIND,
                    syntax_spans=emphasis_syntax_spans,
                    emphasis_spans=tuple(
                        span
                        for span in document_view.emphasis_spans
                        if _range_belongs_to_value(
                            span.outer_start,
                            span.outer_end,
                            value_mappings,
                        )
                    ),
                )
            )

        if syntax_profile.supports(_WILDCARD_KIND):
            wildcard_syntax_spans = tuple(
                span for span in active_syntax_spans if span.kind == _WILDCARD_KIND
            )
            renderer_views.append(
                PromptWildcardRendererView(
                    kind=_WILDCARD_KIND,
                    syntax_spans=wildcard_syntax_spans,
                    wildcard_spans=self._wildcard_renderer_spans(
                        document_view,
                        value_mappings=value_mappings,
                    ),
                )
            )

        if syntax_profile.supports(_LORA_KIND):
            lora_syntax_spans = tuple(
                span for span in active_syntax_spans if span.kind == _LORA_KIND
            )
            lora_renderer_spans = self._lora_renderer_spans(
                document_view,
                value_mappings=value_mappings,
            )
            renderer_views.append(
                PromptLoraRendererView(
                    kind=_LORA_KIND,
                    syntax_spans=lora_syntax_spans,
                    lora_spans=lora_renderer_spans,
                )
            )
            if document_view.lora_spans:
                _log_lora_render_plan_summary(
                    _lora_render_plan_summary(
                        document_view=document_view,
                        syntax_profile=syntax_profile,
                        active_lora_syntax_spans=lora_syntax_spans,
                        lora_renderer_spans=lora_renderer_spans,
                        cache_revision=_object_revision(
                            self._prompt_lora_catalog_service
                        ),
                    )
                )

        render_plan = PromptSyntaxRenderPlan(
            syntax_spans=active_syntax_spans,
            renderer_views=tuple(renderer_views),
            document_semantics_identity=self._document_semantics.identity,
        )
        return render_plan

    def _wildcard_renderer_spans(
        self,
        document_view: PromptDocumentView,
        *,
        value_mappings: tuple[PromptValueMapping, ...],
    ) -> tuple[PromptWildcardRendererSpanView, ...]:
        """Return renderer-ready wildcard spans with current catalog resolution state."""

        wildcard_spans = tuple(
            span
            for span in document_view.wildcard_spans
            if _range_belongs_to_value(
                span.outer_start,
                span.outer_end,
                value_mappings,
            )
        )
        references = tuple(
            PromptWildcardReference(
                identifier=span.identifier,
                wildcard_form=span.wildcard_form,
                csv_column=span.csv_column,
                tag=span.tag,
            )
            for span in wildcard_spans
        )
        resolutions = self._prompt_wildcard_catalog_gateway.resolve_references(
            references
        )
        occurrence_counts = Counter(
            _wildcard_source_key(span) for span in wildcard_spans
        )
        renderer_spans: list[PromptWildcardRendererSpanView] = []
        for wildcard_span, resolution in zip(
            wildcard_spans,
            resolutions,
            strict=True,
        ):
            renderer_spans.append(
                _wildcard_renderer_span_from_views(
                    wildcard_span,
                    resolution,
                    source_occurrence_count=occurrence_counts[
                        _wildcard_source_key(wildcard_span)
                    ],
                )
            )
        return tuple(renderer_spans)

    def _lora_renderer_spans(
        self,
        document_view: PromptDocumentView,
        *,
        value_mappings: tuple[PromptValueMapping, ...],
    ) -> tuple[PromptLoraRendererSpanView, ...]:
        """Return renderer-ready LoRA spans with current catalog metadata."""

        spans = tuple(
            _lora_renderer_span_from_view(
                lora_span,
                self._resolve_lora_catalog_item(lora_span.prompt_name),
            )
            for lora_span in document_view.lora_spans
            if _range_belongs_to_value(
                lora_span.outer_start,
                lora_span.outer_end,
                value_mappings,
            )
        )
        return spans

    def _resolve_lora_catalog_item(
        self,
        prompt_name: str,
    ) -> PromptLoraResolution:
        """Return the catalog item and absence authority for one LoRA name."""

        if self._prompt_lora_catalog_service is None:
            resolution = self._prompt_lora_resolution_service.resolve(prompt_name)
            _log_lora_resolution_result(
                prompt_name,
                resolution=resolution,
                catalog_available=False,
                catalog_lookup_succeeded=False,
            )
            return resolution
        try:
            resolution = self._prompt_lora_resolution_service.resolve(prompt_name)
            _log_lora_resolution_result(
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
            _log_lora_resolution_result(
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


def _log_lora_resolution_result(
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


def _wildcard_renderer_span_from_views(
    wildcard_span: PromptWildcardView,
    resolution: PromptWildcardResolution,
    *,
    source_occurrence_count: int,
) -> PromptWildcardRendererSpanView:
    """Combine one parsed wildcard span with its catalog resolution state."""

    display_tag = _wildcard_display_tag(
        wildcard_span,
        source_occurrence_count=source_occurrence_count,
    )
    tag_is_numeric = _is_numeric_wildcard_tag(display_tag)
    return PromptWildcardRendererSpanView(
        outer_start=wildcard_span.outer_start,
        outer_end=wildcard_span.outer_end,
        content_start=wildcard_span.content_start,
        content_end=wildcard_span.content_end,
        wildcard_form=wildcard_span.wildcard_form,
        identifier=wildcard_span.identifier,
        csv_column=wildcard_span.csv_column,
        tag=wildcard_span.tag,
        exists=resolution.exists,
        matched_csv_column=resolution.matched_csv_column,
        available_csv_columns=resolution.available_csv_columns,
        depth=wildcard_span.depth,
        source_key=_wildcard_source_key(wildcard_span),
        display_text=_wildcard_display_text(wildcard_span, resolution),
        display_tag=display_tag,
        tag_is_explicit=wildcard_span.tag is not None,
        tag_is_numeric=tag_is_numeric,
        can_step_tag=tag_is_numeric,
        source_occurrence_count=source_occurrence_count,
    )


def _wildcard_source_key(wildcard_span: PromptWildcardView) -> str:
    """Return the resolver-aligned wildcard source key used for visual grouping."""

    return f"{wildcard_span.wildcard_form}:{wildcard_span.identifier}"


def _wildcard_display_text(
    wildcard_span: PromptWildcardView,
    resolution: PromptWildcardResolution,
) -> str:
    """Return the inline wildcard label without tag or source-kind badge text."""

    if wildcard_span.wildcard_form != "csv":
        return wildcard_span.identifier
    column = resolution.matched_csv_column or wildcard_span.csv_column
    if column is None:
        return wildcard_span.identifier
    return f"{wildcard_span.identifier}:{column}"


def _wildcard_display_tag(
    wildcard_span: PromptWildcardView,
    *,
    source_occurrence_count: int,
) -> str | None:
    """Return the explicit or display-only wildcard group tag for one span."""

    if wildcard_span.tag is not None:
        return wildcard_span.tag
    if source_occurrence_count > 1:
        return "1"
    return None


def _is_numeric_wildcard_tag(tag: str | None) -> bool:
    """Return whether one wildcard tag supports numeric group stepping."""

    return tag is not None and _NUMERIC_WILDCARD_TAG_PATTERN.fullmatch(tag) is not None


def _lora_renderer_span_from_view(
    lora_span: PromptLoraView,
    resolution: PromptLoraResolution,
) -> PromptLoraRendererSpanView:
    """Combine one parsed LoRA span with optional catalog metadata."""

    catalog_item = resolution.catalog_item
    display_name = (
        _fallback_lora_display_name(lora_span.prompt_name)
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


def _fallback_lora_display_name(prompt_name: str) -> str:
    """Return a basename-derived display name for uncataloged LoRA syntax."""

    normalized_prompt_name = prompt_name.replace("\\", "/")
    return normalized_prompt_name.rsplit("/", maxsplit=1)[-1] or prompt_name


def _lora_render_plan_summary(
    *,
    document_view: PromptDocumentView,
    syntax_profile: PromptSyntaxProfile,
    active_lora_syntax_spans: tuple[PromptSyntaxSpanView, ...],
    lora_renderer_spans: tuple[PromptLoraRendererSpanView, ...],
    cache_revision: str,
) -> _PromptLoraRenderPlanSummary:
    """Return aggregate LoRA render metadata for observability and tests."""

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
    return _PromptLoraRenderPlanSummary(
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


def _log_lora_render_plan_summary(
    summary: _PromptLoraRenderPlanSummary,
) -> None:
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
        non_authoritative_unresolved_count=(summary.non_authoritative_unresolved_count),
        cache_revision=summary.cache_revision,
    )


def _render_plan_cache_key(
    document_view: PromptDocumentView,
    syntax_profile: PromptSyntaxProfile,
    *,
    wildcard_catalog: PromptWildcardCatalogGateway,
    lora_catalog: PromptLoraCatalogLookup | None,
    document_semantics: PromptDocumentSemantics,
) -> PromptProjectionInputCacheKey:
    """Build the pure projection-input cache key for one syntax render request."""

    source_text = document_view.source_text
    return PromptProjectionInputCacheKey(
        source_text_hash=hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
        source_text_length=len(source_text),
        syntax_profile_identity=tuple(syntax_profile.enabled_syntaxes),
        feature_profile_identity=tuple(syntax_profile.enabled_syntaxes),
        wildcard_catalog_revision=_object_revision(wildcard_catalog),
        lora_model_metadata_revision=_object_revision(lora_catalog),
        scene_parsing_version=_PROMPT_SCENE_PARSING_VERSION,
        document_semantics_identity=document_semantics.identity,
    )


def _range_belongs_to_value(
    start: int,
    end: int,
    value_mappings: tuple[PromptValueMapping, ...],
) -> bool:
    """Return whether a complete source range belongs to one prompt value."""

    return _value_id_for_range(start, end, value_mappings) is not None


def _value_id_for_range(
    start: int,
    end: int,
    value_mappings: tuple[PromptValueMapping, ...],
) -> str | None:
    """Return the mapped value id containing one complete source range."""

    for mapping in value_mappings:
        if mapping.source_range.start <= start and end <= mapping.source_range.end:
            return mapping.value_id
    return None


def _object_revision(value: object | None) -> str:
    """Return a stable cache revision string for a catalog-like collaborator."""

    if value is None:
        return "none"
    for attribute_name in ("cache_revision", "revision", "version"):
        raw_revision = getattr(value, attribute_name, None)
        if isinstance(raw_revision, str | int):
            return str(raw_revision)
    return f"identity:{id(value)}"


def clear_prompt_syntax_render_plan_cache() -> None:
    """Clear process-wide pure prompt syntax render-plan cache entries."""

    with _RENDER_PLAN_CACHE_LOCK:
        _RENDER_PLAN_CACHE.clear()


__all__ = [
    "PromptEmphasisRendererView",
    "PromptLoraRendererSpanView",
    "PromptLoraRendererView",
    "PromptProjectionInputCacheKey",
    "PromptSyntaxRenderPlan",
    "PromptSyntaxRendererView",
    "PromptSyntaxService",
    "PromptSyntaxSpanView",
    "PromptWildcardRendererSpanView",
    "PromptWildcardRendererView",
    "clear_prompt_syntax_render_plan_cache",
]

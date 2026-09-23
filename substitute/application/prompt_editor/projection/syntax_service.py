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

"""Orchestrate renderer-ready syntax projection for prompt documents."""

from __future__ import annotations

from time import perf_counter

from substitute.application.ports import PromptWildcardCatalogGateway
from substitute.application.prompt_editor.document.projector import (
    PromptDocumentProjector,
)
from substitute.application.prompt_editor.document.semantics import (
    OrdinaryPromptDocumentSemantics,
    PromptDocumentSemantics,
    PromptValueMapping,
)
from substitute.application.prompt_editor.document.views import (
    PromptDocumentView,
    PromptSyntaxSpanView,
)
from substitute.application.prompt_editor.features.syntax_profile import (
    PromptSyntaxProfile,
)
from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogLookup,
)
from substitute.application.prompt_editor.projection.lora_projection import (
    PromptLoraRendererProjector,
)
from substitute.application.prompt_editor.projection.structured_syntax import (
    PromptStructuredSyntaxProjector,
)
from substitute.application.prompt_editor.projection.syntax_cache import (
    PromptSyntaxRenderPlanCache,
    shared_prompt_syntax_render_plan_cache,
)
from substitute.application.prompt_editor.projection.syntax_models import (
    PromptEmphasisRendererView,
    PromptLoraRendererView,
    PromptSyntaxRendererView,
    PromptSyntaxRenderPlan,
    PromptWildcardRendererView,
)
from substitute.application.prompt_editor.projection.wildcard_projection import (
    PromptWildcardRendererProjector,
)
from substitute.shared.diagnostics.prompt_editor_work import (
    PromptEditorWorkEvent,
    prompt_editor_work_event,
)
from substitute.shared.logging.logger import get_logger, log_debug, log_timing

_EMPHASIS_KIND = "emphasis"
_LORA_KIND = "lora"
_WILDCARD_KIND = "wildcard"
_LOGGER = get_logger("application.prompt_editor.projection.syntax_service")


class PromptSyntaxService:
    """Coordinate document parsing, syntax-family projection, and plan reuse."""

    def __init__(
        self,
        prompt_wildcard_catalog_gateway: PromptWildcardCatalogGateway,
        prompt_lora_catalog_service: PromptLoraCatalogLookup | None = None,
        document_semantics: PromptDocumentSemantics | None = None,
        render_plan_cache: PromptSyntaxRenderPlanCache | None = None,
    ) -> None:
        """Compose syntax projectors around document semantics and shared cache."""

        self._prompt_wildcard_catalog_gateway = prompt_wildcard_catalog_gateway
        self._prompt_lora_catalog_service = prompt_lora_catalog_service
        self._document_semantics = (
            document_semantics or OrdinaryPromptDocumentSemantics()
        )
        self._structured_syntax_projector = PromptStructuredSyntaxProjector(
            document_projector=PromptDocumentProjector(),
            document_semantics=self._document_semantics,
        )
        self._wildcard_projector = PromptWildcardRendererProjector(
            prompt_wildcard_catalog_gateway
        )
        self._lora_projector = PromptLoraRendererProjector(prompt_lora_catalog_service)
        self._render_plan_cache = (
            render_plan_cache or shared_prompt_syntax_render_plan_cache()
        )

    @prompt_editor_work_event(PromptEditorWorkEvent.SYNTAX_RENDER_PLAN_BUILD)
    def build_render_plan(
        self,
        document_view: PromptDocumentView,
        syntax_profile: PromptSyntaxProfile,
    ) -> PromptSyntaxRenderPlan:
        """Build or reuse the complete syntax plan for one document view."""

        cache_key = self._render_plan_cache.key_for(
            document_view,
            syntax_profile,
            wildcard_catalog=self._prompt_wildcard_catalog_gateway,
            lora_catalog=self._prompt_lora_catalog_service,
            document_semantics=self._document_semantics,
        )
        cached, cache_size = self._render_plan_cache.lookup(cache_key)
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
        built = self._build_uncached_render_plan(document_view, syntax_profile)
        render_plan, cache_size = self._render_plan_cache.install(cache_key, built)
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

        self._render_plan_cache.clear()

    def _build_uncached_render_plan(
        self,
        document_view: PromptDocumentView,
        syntax_profile: PromptSyntaxProfile,
    ) -> PromptSyntaxRenderPlan:
        """Build one syntax render plan without consulting the cache."""

        value_mappings = self._value_mappings(document_view.source_text)
        document_view = self._structured_syntax_projector.project(document_view)
        active_syntax_spans = tuple(
            span
            for span in document_view.syntax_spans
            if syntax_profile.supports(span.kind)
            and _range_belongs_to_value(span.start, span.end, value_mappings)
        )
        renderer_views: list[PromptSyntaxRendererView] = []
        if syntax_profile.supports(_EMPHASIS_KIND):
            renderer_views.append(
                self._emphasis_renderer_view(
                    document_view,
                    active_syntax_spans,
                    value_mappings,
                )
            )
        if syntax_profile.supports(_WILDCARD_KIND):
            renderer_views.append(
                self._wildcard_renderer_view(
                    document_view,
                    active_syntax_spans,
                    value_mappings,
                )
            )
        if syntax_profile.supports(_LORA_KIND):
            lora_view = self._lora_renderer_view(
                document_view,
                syntax_profile,
                active_syntax_spans,
                value_mappings,
            )
            renderer_views.append(lora_view)
        return PromptSyntaxRenderPlan(
            syntax_spans=active_syntax_spans,
            renderer_views=tuple(renderer_views),
            document_semantics_identity=self._document_semantics.identity,
        )

    def _value_mappings(self, source_text: str) -> tuple[PromptValueMapping, ...]:
        """Return structured or ordinary value boundaries for source filtering."""

        if self._document_semantics.uses_structured_prompt_values:
            return self._document_semantics.value_mappings_for_text(source_text)
        return OrdinaryPromptDocumentSemantics().value_mappings_for_text(source_text)

    def _emphasis_renderer_view(
        self,
        document_view: PromptDocumentView,
        active_syntax_spans: tuple[PromptSyntaxSpanView, ...],
        value_mappings: tuple[PromptValueMapping, ...],
    ) -> PromptEmphasisRendererView:
        """Return the emphasis renderer view for one projected document."""

        return PromptEmphasisRendererView(
            kind=_EMPHASIS_KIND,
            syntax_spans=tuple(
                span for span in active_syntax_spans if span.kind == _EMPHASIS_KIND
            ),
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

    def _wildcard_renderer_view(
        self,
        document_view: PromptDocumentView,
        active_syntax_spans: tuple[PromptSyntaxSpanView, ...],
        value_mappings: tuple[PromptValueMapping, ...],
    ) -> PromptWildcardRendererView:
        """Return the wildcard renderer view for one projected document."""

        wildcard_spans = tuple(
            span
            for span in document_view.wildcard_spans
            if _range_belongs_to_value(
                span.outer_start,
                span.outer_end,
                value_mappings,
            )
        )
        return PromptWildcardRendererView(
            kind=_WILDCARD_KIND,
            syntax_spans=tuple(
                span for span in active_syntax_spans if span.kind == _WILDCARD_KIND
            ),
            wildcard_spans=self._wildcard_projector.project(wildcard_spans),
        )

    def _lora_renderer_view(
        self,
        document_view: PromptDocumentView,
        syntax_profile: PromptSyntaxProfile,
        active_syntax_spans: tuple[PromptSyntaxSpanView, ...],
        value_mappings: tuple[PromptValueMapping, ...],
    ) -> PromptLoraRendererView:
        """Return the LoRA renderer view and publish its resolution summary."""

        lora_syntax_spans = tuple(
            span for span in active_syntax_spans if span.kind == _LORA_KIND
        )
        lora_spans = tuple(
            span
            for span in document_view.lora_spans
            if _range_belongs_to_value(
                span.outer_start,
                span.outer_end,
                value_mappings,
            )
        )
        renderer_spans = self._lora_projector.project(lora_spans)
        if document_view.lora_spans:
            self._lora_projector.log_render_plan_summary(
                document_view=document_view,
                syntax_profile=syntax_profile,
                active_lora_syntax_spans=lora_syntax_spans,
                lora_renderer_spans=renderer_spans,
                cache_revision=self._render_plan_cache.revision_for(
                    self._prompt_lora_catalog_service
                ),
            )
        return PromptLoraRendererView(
            kind=_LORA_KIND,
            syntax_spans=lora_syntax_spans,
            lora_spans=renderer_spans,
        )


def _range_belongs_to_value(
    start: int,
    end: int,
    value_mappings: tuple[PromptValueMapping, ...],
) -> bool:
    """Return whether a complete source range belongs to one prompt value."""

    return any(
        mapping.source_range.start <= start and end <= mapping.source_range.end
        for mapping in value_mappings
    )


__all__ = ["PromptSyntaxService"]

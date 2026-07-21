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

"""Project prompt syntax from decoded values into structured source text."""

from __future__ import annotations

from substitute.domain.prompt import SourceRange

from .prompt_document_projector import PromptDocumentProjector
from .prompt_document_semantics import PromptDocumentSemantics, PromptValueMapping
from .prompt_document_views import (
    PromptDocumentView,
    PromptEmphasisView,
    PromptLoraView,
    PromptSyntaxSpanView,
    PromptWildcardView,
)


class PromptStructuredSyntaxProjector:
    """Parse logical prompt values and remap their syntax to raw source ranges."""

    def __init__(
        self,
        *,
        document_projector: PromptDocumentProjector,
        document_semantics: PromptDocumentSemantics,
    ) -> None:
        """Store the canonical prompt parser and document semantics owner."""

        self._document_projector = document_projector
        self._document_semantics = document_semantics

    def project(self, document_view: PromptDocumentView) -> PromptDocumentView:
        """Decode structured prompt values and map their syntax to source."""

        if not self._document_semantics.uses_structured_prompt_values:
            return document_view
        value_mappings = self._document_semantics.value_mappings_for_text(
            document_view.source_text
        )
        local_views = tuple(
            (
                mapping,
                self._document_projector.build_document_view(mapping.logical_text),
            )
            for mapping in value_mappings
        )
        return PromptDocumentView(
            source_text=document_view.source_text,
            segments=document_view.segments,
            emphasis_spans=tuple(
                _map_emphasis(mapping, span)
                for mapping, local_view in local_views
                for span in local_view.emphasis_spans
            ),
            wildcard_spans=tuple(
                _map_wildcard(mapping, span)
                for mapping, local_view in local_views
                for span in local_view.wildcard_spans
            ),
            lora_spans=tuple(
                _map_lora(mapping, span)
                for mapping, local_view in local_views
                for span in local_view.lora_spans
            ),
            syntax_spans=tuple(
                _map_syntax_span(mapping, span)
                for mapping, local_view in local_views
                for span in local_view.syntax_spans
            ),
            has_trailing_comma=document_view.has_trailing_comma,
        )


def _map_emphasis(
    mapping: PromptValueMapping,
    span: PromptEmphasisView,
) -> PromptEmphasisView:
    """Map one logical emphasis view into raw document coordinates."""

    outer = _map_range(mapping, span.outer_start, span.outer_end)
    content = _map_range(mapping, span.content_start, span.content_end)
    weight = _map_range(mapping, span.weight_start, span.weight_end)
    return PromptEmphasisView(
        outer_start=outer.start,
        outer_end=outer.end,
        content_start=content.start,
        content_end=content.end,
        weight_start=weight.start,
        weight_end=weight.end,
        weight=span.weight,
        weight_text=span.weight_text,
        depth=span.depth,
    )


def _map_wildcard(
    mapping: PromptValueMapping,
    span: PromptWildcardView,
) -> PromptWildcardView:
    """Map one logical wildcard view into raw document coordinates."""

    outer = _map_range(mapping, span.outer_start, span.outer_end)
    content = _map_range(mapping, span.content_start, span.content_end)
    return PromptWildcardView(
        outer_start=outer.start,
        outer_end=outer.end,
        content_start=content.start,
        content_end=content.end,
        wildcard_form=span.wildcard_form,
        identifier=span.identifier,
        csv_column=span.csv_column,
        tag=span.tag,
        depth=span.depth,
    )


def _map_lora(mapping: PromptValueMapping, span: PromptLoraView) -> PromptLoraView:
    """Map one logical LoRA view into raw document coordinates."""

    outer = _map_range(mapping, span.outer_start, span.outer_end)
    name = _map_range(mapping, span.name_start, span.name_end)
    first_weight = _map_range(
        mapping,
        span.first_weight_start,
        span.first_weight_end,
    )
    second_weight = _map_optional_range(
        mapping,
        span.second_weight_start,
        span.second_weight_end,
    )
    block_weights = _map_optional_range(
        mapping,
        span.block_weights_start,
        span.block_weights_end,
    )
    return PromptLoraView(
        outer_start=outer.start,
        outer_end=outer.end,
        name_start=name.start,
        name_end=name.end,
        first_weight_start=first_weight.start,
        first_weight_end=first_weight.end,
        first_weight=span.first_weight,
        first_weight_text=span.first_weight_text,
        second_weight_start=(None if second_weight is None else second_weight.start),
        second_weight_end=None if second_weight is None else second_weight.end,
        second_weight=span.second_weight,
        second_weight_text=span.second_weight_text,
        block_weights_start=(None if block_weights is None else block_weights.start),
        block_weights_end=None if block_weights is None else block_weights.end,
        prompt_name=span.prompt_name,
        depth=span.depth,
    )


def _map_syntax_span(
    mapping: PromptValueMapping,
    span: PromptSyntaxSpanView,
) -> PromptSyntaxSpanView:
    """Map one generic logical syntax span into raw document coordinates."""

    source_range = _map_range(mapping, span.start, span.end)
    return PromptSyntaxSpanView(
        kind=span.kind,
        start=source_range.start,
        end=source_range.end,
        depth=span.depth,
    )


def _map_range(mapping: PromptValueMapping, start: int, end: int) -> SourceRange:
    """Map one half-open logical range through a prompt value mapping."""

    return mapping.source_range_for_logical_range(SourceRange(start, end))


def _map_optional_range(
    mapping: PromptValueMapping,
    start: int | None,
    end: int | None,
) -> SourceRange | None:
    """Map one optional logical range when both endpoints are available."""

    if start is None or end is None:
        return None
    return _map_range(mapping, start, end)


__all__ = ["PromptStructuredSyntaxProjector"]

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

"""Resolve parsed wildcard spans into renderer-facing projections."""

from __future__ import annotations

from collections import Counter
import re

from substitute.application.ports import (
    PromptWildcardCatalogGateway,
    PromptWildcardReference,
    PromptWildcardResolution,
)
from substitute.application.prompt_editor.document.views import PromptWildcardView
from substitute.application.prompt_editor.projection.syntax_models import (
    PromptWildcardRendererSpanView,
)

_NUMERIC_WILDCARD_TAG_PATTERN = re.compile(r"^[1-9][0-9]*$")


class PromptWildcardRendererProjector:
    """Project wildcard spans with current catalog resolution state."""

    def __init__(self, catalog_gateway: PromptWildcardCatalogGateway) -> None:
        """Store the catalog used to resolve wildcard references in batches."""

        self._catalog_gateway = catalog_gateway

    def project(
        self,
        wildcard_spans: tuple[PromptWildcardView, ...],
    ) -> tuple[PromptWildcardRendererSpanView, ...]:
        """Return renderer-ready wildcard spans in source order."""

        references = tuple(
            PromptWildcardReference(
                identifier=span.identifier,
                wildcard_form=span.wildcard_form,
                csv_column=span.csv_column,
                tag=span.tag,
            )
            for span in wildcard_spans
        )
        resolutions = self._catalog_gateway.resolve_references(references)
        occurrence_counts = Counter(_source_key(span) for span in wildcard_spans)
        return tuple(
            _renderer_span(
                wildcard_span,
                resolution,
                source_occurrence_count=occurrence_counts[_source_key(wildcard_span)],
            )
            for wildcard_span, resolution in zip(
                wildcard_spans,
                resolutions,
                strict=True,
            )
        )


def _renderer_span(
    wildcard_span: PromptWildcardView,
    resolution: PromptWildcardResolution,
    *,
    source_occurrence_count: int,
) -> PromptWildcardRendererSpanView:
    """Combine one parsed wildcard span with its catalog resolution state."""

    display_tag = _display_tag(
        wildcard_span,
        source_occurrence_count=source_occurrence_count,
    )
    tag_is_numeric = is_numeric_wildcard_tag(display_tag)
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
        source_key=_source_key(wildcard_span),
        display_text=_display_text(wildcard_span, resolution),
        display_tag=display_tag,
        tag_is_explicit=wildcard_span.tag is not None,
        tag_is_numeric=tag_is_numeric,
        can_step_tag=tag_is_numeric,
        source_occurrence_count=source_occurrence_count,
    )


def _source_key(wildcard_span: PromptWildcardView) -> str:
    """Return the resolver-aligned source key used for visual grouping."""

    return f"{wildcard_span.wildcard_form}:{wildcard_span.identifier}"


def _display_text(
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


def _display_tag(
    wildcard_span: PromptWildcardView,
    *,
    source_occurrence_count: int,
) -> str | None:
    """Return the explicit or display-only group tag for one wildcard span."""

    if wildcard_span.tag is not None:
        return wildcard_span.tag
    if source_occurrence_count > 1:
        return "1"
    return None


def is_numeric_wildcard_tag(tag: str | None) -> bool:
    """Return whether one wildcard tag supports numeric group stepping."""

    return tag is not None and _NUMERIC_WILDCARD_TAG_PATTERN.fullmatch(tag) is not None


__all__ = ["PromptWildcardRendererProjector", "is_numeric_wildcard_tag"]

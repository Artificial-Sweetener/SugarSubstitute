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

"""Translate autocomplete queries between decoded values and structured source."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.domain.prompt import SourceRange

from .prompt_autocomplete_queries import (
    PromptAutocompleteFallbackQuery,
    PromptAutocompleteQuery,
    PromptWildcardAutocompleteQuery,
)
from .prompt_document_semantics import PromptDocumentSemantics, PromptValueMapping
from .prompt_lora_autocomplete_service import PromptLoraAutocompleteQuery


@dataclass(frozen=True, slots=True)
class PromptStructuredAutocompleteContext:
    """Expose one decoded prompt value and its logical caret position."""

    mapping: PromptValueMapping
    logical_cursor_position: int

    def map_plain_query(
        self,
        query: PromptAutocompleteQuery | None,
    ) -> PromptAutocompleteQuery | None:
        """Map one decoded plain-tag query into raw source coordinates."""

        if query is None:
            return None
        return PromptAutocompleteQuery(
            prefix=query.prefix,
            word_start=self._source_position(query.word_start),
            word_end=self._source_position(query.word_end),
            active_tag_end=self._source_position(query.active_tag_end),
            fallback_query=self._map_fallback_query(query.fallback_query),
        )

    def map_wildcard_query(
        self,
        query: PromptWildcardAutocompleteQuery | None,
    ) -> PromptWildcardAutocompleteQuery | None:
        """Map one decoded wildcard query into raw source coordinates."""

        if query is None:
            return None
        return PromptWildcardAutocompleteQuery(
            prefix=query.prefix,
            opener_start=self._source_position(query.opener_start),
            content_start=self._source_position(query.content_start),
            cursor_position=self._source_position(query.cursor_position),
            replacement_end=self._source_position(query.replacement_end),
        )

    def map_lora_query(
        self,
        query: PromptLoraAutocompleteQuery | None,
    ) -> PromptLoraAutocompleteQuery | None:
        """Map one decoded LoRA query into raw source coordinates."""

        if query is None:
            return None
        return PromptLoraAutocompleteQuery(
            query_text=query.query_text,
            token_start=self._source_position(query.token_start),
            token_end=self._source_position(query.token_end),
            name_start=self._source_position(query.name_start),
            name_end=self._source_position(query.name_end),
            replacement_start=self._source_position(query.replacement_start),
            replacement_end=self._source_position(query.replacement_end),
            typed_weight_text=query.typed_weight_text,
            has_closing_bracket=query.has_closing_bracket,
        )

    def _map_fallback_query(
        self,
        query: PromptAutocompleteFallbackQuery | None,
    ) -> PromptAutocompleteFallbackQuery | None:
        """Map one optional decoded fallback query into raw coordinates."""

        if query is None:
            return None
        return PromptAutocompleteFallbackQuery(
            prefix=query.prefix,
            word_start=self._source_position(query.word_start),
            word_end=self._source_position(query.word_end),
            active_tag_end=self._source_position(query.active_tag_end),
        )

    def _source_position(self, logical_position: int) -> int:
        """Return the raw caret position for one decoded value position."""

        return self.mapping.source_range_for_logical_range(
            SourceRange(logical_position, logical_position)
        ).start


def structured_autocomplete_context_at_cursor(
    document_semantics: PromptDocumentSemantics,
    *,
    source_text: str,
    source_cursor_position: int,
) -> PromptStructuredAutocompleteContext | None:
    """Return a decoded autocomplete context for one structured-source caret."""

    mapping = document_semantics.value_mapping_at_position(
        source_text,
        source_cursor_position,
    )
    if mapping is None:
        return None
    try:
        logical_cursor_position = mapping.logical_range_for_source_range(
            SourceRange(source_cursor_position, source_cursor_position)
        ).start
    except ValueError:
        return None
    return PromptStructuredAutocompleteContext(
        mapping=mapping,
        logical_cursor_position=logical_cursor_position,
    )


__all__ = [
    "PromptStructuredAutocompleteContext",
    "structured_autocomplete_context_at_cursor",
]

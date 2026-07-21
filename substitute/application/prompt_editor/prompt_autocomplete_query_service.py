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

"""Resolve prompt autocomplete query ranges from prompt document views."""

from __future__ import annotations

import re
import time

from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.domain.prompt import PROMPT_SCENE_MARKER
from substitute.shared.logging.logger import elapsed_ms_since, get_logger, log_debug

from .prompt_autocomplete_queries import (
    PromptAutocompleteQuery,
    PromptSceneAutocompleteQuery,
    PromptWildcardAutocompleteQuery,
)
from .prompt_autocomplete_tag_ranges import autocomplete_tag_range_at_cursor
from .prompt_document_projector import PromptDocumentProjector
from .prompt_document_semantics import (
    OrdinaryPromptDocumentSemantics,
    PromptDocumentSemantics,
)
from .prompt_document_selection_service import PromptDocumentSelectionService
from .prompt_document_view_mapper import unescape_literal_parentheses_for_display
from .prompt_document_views import PromptDocumentView
from .prompt_lora_autocomplete_service import PromptLoraAutocompleteQuery
from .prompt_structured_autocomplete_mapper import (
    PromptStructuredAutocompleteContext,
    structured_autocomplete_context_at_cursor,
)
from .prompt_text_ranges import (
    line_end_within_bounds,
    line_start_within_bounds,
    line_visible_start,
)

_LOGGER = get_logger("application.prompt_editor.prompt_autocomplete_query_service")
_VALID_LORA_AUTOCOMPLETE_WEIGHT_RE = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)")


def autocomplete_replacement_text(tag: str) -> str:
    """Return the prompt text inserted when one autocomplete tag is accepted."""

    return re.sub(r"([()])", r"\\\1", tag.replace("_", " "))


def filter_noop_autocomplete_suggestions(
    *,
    text: str,
    query: PromptAutocompleteQuery,
    suggestions: tuple[PromptAutocompleteSuggestion, ...],
) -> tuple[PromptAutocompleteSuggestion, ...]:
    """Drop autocomplete suggestions that already match the current replacement slice."""

    started_at = time.perf_counter()
    current_slice = text[query.word_start : query.active_tag_end]
    normalized_current_slice = _normalize_autocomplete_comparison_text(current_slice)
    filtered_suggestions = tuple(
        suggestion
        for suggestion in suggestions
        if _normalize_autocomplete_comparison_text(
            autocomplete_replacement_text(suggestion.tag)
        )
        != normalized_current_slice
    )
    _log_autocomplete_resolution(
        "filter_noop_autocomplete_suggestions",
        started_at=started_at,
        text_length=len(text),
        suggestion_count=len(suggestions),
        result_count=len(filtered_suggestions),
    )
    return filtered_suggestions


class PromptAutocompleteQueryService:
    """Own prompt-aware autocomplete query and replacement-range behavior."""

    def __init__(
        self,
        *,
        document_projector: PromptDocumentProjector | None = None,
        selection_service: PromptDocumentSelectionService | None = None,
        document_semantics: PromptDocumentSemantics | None = None,
    ) -> None:
        """Store document and selection collaborators used by query resolution."""

        self._document_projector = document_projector or PromptDocumentProjector()
        self._selection_service = selection_service or PromptDocumentSelectionService()
        self._document_semantics = (
            document_semantics or OrdinaryPromptDocumentSemantics()
        )

    def autocomplete_query_at_cursor(
        self,
        document_view: PromptDocumentView,
        *,
        text: str,
        cursor_position: int,
        has_selection: bool,
        minimum_prefix_length: int,
    ) -> PromptAutocompleteQuery | None:
        """Resolve one prompt-aware autocomplete query from the current caret state."""

        started_at = time.perf_counter()
        if has_selection or cursor_position < 0 or cursor_position > len(text):
            _log_autocomplete_resolution(
                "autocomplete_query_at_cursor",
                started_at=started_at,
                text_length=len(text),
                cursor_position=cursor_position,
                has_selection=has_selection,
                matched=False,
            )
            return None
        structured_context = self._structured_context(text, cursor_position)
        if self._document_semantics.uses_structured_prompt_values:
            if structured_context is None:
                return None
            text = structured_context.mapping.logical_text
            cursor_position = structured_context.logical_cursor_position
            current_document_view = self._document_projector.build_document_view(text)
        else:
            current_document_view = document_view
            if current_document_view.source_text != text:
                current_document_view = self._document_projector.build_document_view(
                    text
                )

        segment = self._selection_service.segment_at_position(
            current_document_view,
            cursor_position,
        )
        if segment is None or cursor_position < segment.selection_start:
            _log_autocomplete_resolution(
                "autocomplete_query_at_cursor",
                started_at=started_at,
                text_length=len(text),
                cursor_position=cursor_position,
                has_selection=has_selection,
                matched=False,
            )
            return None

        tag_range = autocomplete_tag_range_at_cursor(
            text=text,
            document_view=current_document_view,
            segment=segment,
            cursor_position=cursor_position,
            minimum_prefix_length=minimum_prefix_length,
        )
        if tag_range is None:
            _log_autocomplete_resolution(
                "autocomplete_query_at_cursor",
                started_at=started_at,
                text_length=len(text),
                cursor_position=cursor_position,
                has_selection=has_selection,
                segment_index=segment.index,
                matched=False,
            )
            return None
        query = PromptAutocompleteQuery(
            prefix=tag_range.prefix,
            word_start=tag_range.replacement_start,
            word_end=tag_range.cursor_position,
            active_tag_end=tag_range.active_tag_end,
            fallback_query=tag_range.fallback_query,
        )
        _log_autocomplete_resolution(
            "autocomplete_query_at_cursor",
            started_at=started_at,
            text_length=len(text),
            cursor_position=cursor_position,
            has_selection=has_selection,
            segment_index=segment.index,
            matched=True,
            result_type="plain",
        )
        return (
            query
            if structured_context is None
            else structured_context.map_plain_query(query)
        )

    def wildcard_autocomplete_query_at_cursor(
        self,
        *,
        text: str,
        cursor_position: int,
        has_selection: bool,
    ) -> PromptWildcardAutocompleteQuery | None:
        """Resolve a curly wildcard autocomplete query from the caret state."""

        started_at = time.perf_counter()
        if has_selection or cursor_position < 0 or cursor_position > len(text):
            _log_autocomplete_resolution(
                "wildcard_autocomplete_query_at_cursor",
                started_at=started_at,
                text_length=len(text),
                cursor_position=cursor_position,
                has_selection=has_selection,
                matched=False,
            )
            return None
        structured_context = self._structured_context(text, cursor_position)
        if self._document_semantics.uses_structured_prompt_values:
            if structured_context is None:
                return None
            text = structured_context.mapping.logical_text
            cursor_position = structured_context.logical_cursor_position
        line_start = line_start_within_bounds(
            text,
            lower_bound=0,
            position=cursor_position,
        )
        line_end = line_end_within_bounds(
            text,
            position=cursor_position,
            upper_bound=len(text),
        )
        opener_start = text.rfind("{", line_start, cursor_position)
        if opener_start < 0:
            _log_autocomplete_resolution(
                "wildcard_autocomplete_query_at_cursor",
                started_at=started_at,
                text_length=len(text),
                cursor_position=cursor_position,
                has_selection=has_selection,
                matched=False,
            )
            return None

        typed_content = text[opener_start + 1 : cursor_position]
        if not _is_wildcard_autocomplete_content(typed_content):
            _log_autocomplete_resolution(
                "wildcard_autocomplete_query_at_cursor",
                started_at=started_at,
                text_length=len(text),
                cursor_position=cursor_position,
                has_selection=has_selection,
                matched=False,
            )
            return None

        closing_index = text.find("}", cursor_position, line_end)
        trailing_end = closing_index if closing_index >= 0 else line_end
        if text[cursor_position:trailing_end].strip():
            _log_autocomplete_resolution(
                "wildcard_autocomplete_query_at_cursor",
                started_at=started_at,
                text_length=len(text),
                cursor_position=cursor_position,
                has_selection=has_selection,
                matched=False,
            )
            return None

        query = PromptWildcardAutocompleteQuery(
            prefix=typed_content,
            opener_start=opener_start,
            content_start=opener_start + 1,
            cursor_position=cursor_position,
            replacement_end=closing_index + 1
            if closing_index >= 0
            else cursor_position,
        )
        _log_autocomplete_resolution(
            "wildcard_autocomplete_query_at_cursor",
            started_at=started_at,
            text_length=len(text),
            cursor_position=cursor_position,
            has_selection=has_selection,
            matched=True,
            result_type="wildcard",
        )
        return (
            query
            if structured_context is None
            else structured_context.map_wildcard_query(query)
        )

    def scene_autocomplete_query_at_cursor(
        self,
        *,
        text: str,
        cursor_position: int,
        has_selection: bool,
    ) -> PromptSceneAutocompleteQuery | None:
        """Resolve a line-start scene autocomplete query from the caret state."""

        started_at = time.perf_counter()
        if not self._document_semantics.scenes_enabled:
            return None
        if has_selection or cursor_position < 0 or cursor_position > len(text):
            _log_autocomplete_resolution(
                "scene_autocomplete_query_at_cursor",
                started_at=started_at,
                text_length=len(text),
                cursor_position=cursor_position,
                has_selection=has_selection,
                matched=False,
            )
            return None

        line_start = line_start_within_bounds(
            text,
            lower_bound=0,
            position=cursor_position,
        )
        line_end = line_end_within_bounds(
            text,
            position=cursor_position,
            upper_bound=len(text),
        )
        marker_start = line_visible_start(
            text,
            line_start=line_start,
            position=line_end,
        )
        marker_end = marker_start + len(PROMPT_SCENE_MARKER)
        if (
            marker_end > line_end
            or text[marker_start:marker_end] != PROMPT_SCENE_MARKER
        ):
            _log_autocomplete_resolution(
                "scene_autocomplete_query_at_cursor",
                started_at=started_at,
                text_length=len(text),
                cursor_position=cursor_position,
                has_selection=has_selection,
                matched=False,
            )
            return None
        title_start = marker_end
        if cursor_position < title_start or text[cursor_position:line_end].strip():
            _log_autocomplete_resolution(
                "scene_autocomplete_query_at_cursor",
                started_at=started_at,
                text_length=len(text),
                cursor_position=cursor_position,
                has_selection=has_selection,
                matched=False,
            )
            return None
        query = PromptSceneAutocompleteQuery(
            prefix=text[title_start:cursor_position],
            marker_start=marker_start,
            title_start=title_start,
            cursor_position=cursor_position,
            replacement_end=cursor_position,
        )
        _log_autocomplete_resolution(
            "scene_autocomplete_query_at_cursor",
            started_at=started_at,
            text_length=len(text),
            cursor_position=cursor_position,
            has_selection=has_selection,
            matched=True,
            result_type="scene",
        )
        return query

    def lora_autocomplete_query_at_cursor(
        self,
        *,
        text: str,
        cursor_position: int,
        has_selection: bool,
    ) -> PromptLoraAutocompleteQuery | None:
        """Resolve a LoRA schedule autocomplete query from the caret state."""

        started_at = time.perf_counter()
        if has_selection or cursor_position < 0 or cursor_position > len(text):
            _log_autocomplete_resolution(
                "lora_autocomplete_query_at_cursor",
                started_at=started_at,
                text_length=len(text),
                cursor_position=cursor_position,
                has_selection=has_selection,
                matched=False,
            )
            return None
        structured_context = self._structured_context(text, cursor_position)
        if self._document_semantics.uses_structured_prompt_values:
            if structured_context is None:
                return None
            text = structured_context.mapping.logical_text
            cursor_position = structured_context.logical_cursor_position
        token_start = text.casefold().rfind("<lora:", 0, cursor_position + 1)
        if token_start < 0 or ">" in text[token_start:cursor_position]:
            _log_autocomplete_resolution(
                "lora_autocomplete_query_at_cursor",
                started_at=started_at,
                text_length=len(text),
                cursor_position=cursor_position,
                has_selection=has_selection,
                matched=False,
            )
            return None

        name_start = token_start + len("<lora:")
        if cursor_position < name_start:
            _log_autocomplete_resolution(
                "lora_autocomplete_query_at_cursor",
                started_at=started_at,
                text_length=len(text),
                cursor_position=cursor_position,
                has_selection=has_selection,
                matched=False,
            )
            return None

        closing_index = _lora_closing_index_for_autocomplete(
            text,
            token_start=token_start,
            name_start=name_start,
        )
        has_closing_bracket = closing_index >= 0
        logical_token_end = (
            closing_index + 1
            if has_closing_bracket
            else _unterminated_lora_token_end(text, cursor_position)
        )
        if has_closing_bracket and cursor_position > closing_index:
            _log_autocomplete_resolution(
                "lora_autocomplete_query_at_cursor",
                started_at=started_at,
                text_length=len(text),
                cursor_position=cursor_position,
                has_selection=has_selection,
                matched=False,
            )
            return None

        token_body_end = closing_index if has_closing_bracket else logical_token_end
        first_separator = text.find(":", name_start, token_body_end)
        if first_separator >= 0:
            if cursor_position > first_separator:
                _log_autocomplete_resolution(
                    "lora_autocomplete_query_at_cursor",
                    started_at=started_at,
                    text_length=len(text),
                    cursor_position=cursor_position,
                    has_selection=has_selection,
                    matched=False,
                )
                return None
            typed_weight_text = _lora_weight_text_after_separator(
                text,
                separator_index=first_separator,
                token_body_end=token_body_end,
            )
        else:
            typed_weight_text = None

        query = PromptLoraAutocompleteQuery(
            query_text=text[name_start:cursor_position],
            token_start=token_start,
            token_end=logical_token_end,
            name_start=name_start,
            name_end=cursor_position,
            replacement_start=token_start,
            replacement_end=logical_token_end,
            typed_weight_text=typed_weight_text,
            has_closing_bracket=has_closing_bracket,
        )
        _log_autocomplete_resolution(
            "lora_autocomplete_query_at_cursor",
            started_at=started_at,
            text_length=len(text),
            cursor_position=cursor_position,
            has_selection=has_selection,
            matched=True,
            result_type="lora",
        )
        return (
            query
            if structured_context is None
            else structured_context.map_lora_query(query)
        )

    def _structured_context(
        self,
        text: str,
        cursor_position: int,
    ) -> PromptStructuredAutocompleteContext | None:
        """Return decoded value context when active source is structured."""

        if not self._document_semantics.uses_structured_prompt_values:
            return None
        return structured_autocomplete_context_at_cursor(
            self._document_semantics,
            source_text=text,
            source_cursor_position=cursor_position,
        )


def _normalize_autocomplete_comparison_text(text: str) -> str:
    """Normalize prompt text for semantic autocomplete no-op comparisons."""

    unescaped_text = unescape_literal_parentheses_for_display(text)
    collapsed_text = " ".join(unescaped_text.replace("_", " ").split())
    return collapsed_text.casefold()


def _is_wildcard_autocomplete_content(text: str) -> bool:
    """Return whether typed wildcard content is safe to complete as an identifier."""

    if any(character in text for character in "{}"):
        return False
    if "," in text:
        return False
    return not any(character.isspace() for character in text)


def _unterminated_lora_token_end(
    text: str,
    cursor_position: int,
    *,
    upper_bound: int | None = None,
) -> int:
    """Return a conservative replacement end for an unterminated LoRA token."""

    index = cursor_position
    token_limit = len(text) if upper_bound is None else min(len(text), upper_bound)
    while index < token_limit and text[index] not in ",\r\n\t ":
        index += 1
    return index


def _lora_closing_index_for_autocomplete(
    text: str,
    *,
    token_start: int,
    name_start: int,
    upper_bound: int | None = None,
) -> int:
    """Return the current LoRA closer without crossing into a later token."""

    search_end = len(text) if upper_bound is None else upper_bound
    closing_index = text.find(">", name_start, search_end)
    if closing_index < 0:
        return -1
    nested_opener = text.find("<", token_start + 1, closing_index)
    if nested_opener >= 0:
        return -1
    return closing_index


def _lora_weight_text_after_separator(
    text: str,
    *,
    separator_index: int,
    token_body_end: int,
) -> str | None:
    """Return the first LoRA weight text after the name separator."""

    weight_start = separator_index + 1
    second_separator = text.find(":", weight_start, token_body_end)
    weight_end = token_body_end if second_separator < 0 else second_separator
    weight_text = text[weight_start:weight_end].strip()
    if not weight_text:
        return None
    if _VALID_LORA_AUTOCOMPLETE_WEIGHT_RE.fullmatch(weight_text) is None:
        return None
    return weight_text


def _log_autocomplete_resolution(
    operation: str,
    *,
    started_at: float,
    text_length: int,
    cursor_position: int | None = None,
    has_selection: bool | None = None,
    segment_index: int | None = None,
    matched: bool | None = None,
    result_type: str | None = None,
    suggestion_count: int | None = None,
    result_count: int | None = None,
) -> None:
    """Log one prompt-safe autocomplete query resolution."""

    context: dict[str, object] = {
        "operation": operation,
        "text_length": text_length,
        "elapsed_ms": f"{elapsed_ms_since(started_at):.3f}",
    }
    if cursor_position is not None:
        context["cursor_position"] = cursor_position
    if has_selection is not None:
        context["has_selection"] = has_selection
    if segment_index is not None:
        context["segment_index"] = segment_index
    if matched is not None:
        context["matched"] = matched
    if result_type is not None:
        context["result_type"] = result_type
    if suggestion_count is not None:
        context["suggestion_count"] = suggestion_count
    if result_count is not None:
        context["result_count"] = result_count
    log_debug(
        _LOGGER,
        "Prompt autocomplete query resolved",
        **context,
    )


__all__ = [
    "PromptAutocompleteQueryService",
    "autocomplete_replacement_text",
    "filter_noop_autocomplete_suggestions",
]

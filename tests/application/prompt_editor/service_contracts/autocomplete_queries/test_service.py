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

"""Service-level tests for the prompt editor application layer."""

from __future__ import annotations


from substitute.application.prompt_editor.autocomplete.queries import (
    PromptAutocompleteFallbackQuery,
    PromptAutocompleteQuery,
)
from substitute.application.prompt_editor.autocomplete.query_service import (
    autocomplete_replacement_text,
    filter_noop_autocomplete_suggestions,
)
from substitute.application.prompt_editor.document.service import (
    PromptDocumentService,
)
from substitute.application.ports import (
    PromptAutocompleteSuggestion,
)


def test_prompt_document_service_builds_prompt_aware_autocomplete_queries() -> None:
    """Autocomplete queries should use parsed segment bounds instead of raw comma scanning."""

    document_service = PromptDocumentService()
    text = "1girl, long ha"
    document_view = document_service.build_document_view(text)

    query = document_service.autocomplete_query_at_cursor(
        document_view,
        text=text,
        cursor_position=len(text),
        has_selection=False,
        minimum_prefix_length=2,
    )

    assert query is not None
    assert (query.prefix, query.word_start, query.word_end, query.active_tag_end) == (
        "long ha",
        7,
        14,
        14,
    )
    assert query.fallback_query == PromptAutocompleteFallbackQuery(
        prefix="ha",
        word_start=12,
        word_end=14,
        active_tag_end=14,
    )


def test_prompt_document_service_autocomplete_query_ignores_nested_commas() -> None:
    """Quoted and bracketed commas should not split the active autocomplete segment."""

    document_service = PromptDocumentService()
    text = '"cat, dog", [bird, fish], long ha'
    document_view = document_service.build_document_view(text)

    query = document_service.autocomplete_query_at_cursor(
        document_view,
        text=text,
        cursor_position=len(text),
        has_selection=False,
        minimum_prefix_length=2,
    )

    assert query is not None
    assert query.prefix == "long ha"
    assert query.word_start == text.index("long ha")
    assert query.word_end == len(text)
    assert query.active_tag_end == len(text)


def test_prompt_document_service_autocomplete_query_ignores_commas_inside_braces() -> (
    None
):
    """Brace placeholders should preserve the active segment boundary for autocomplete."""

    document_service = PromptDocumentService()
    text = "{animal, texture}, long ha"
    document_view = document_service.build_document_view(text)

    query = document_service.autocomplete_query_at_cursor(
        document_view,
        text=text,
        cursor_position=len(text),
        has_selection=False,
        minimum_prefix_length=2,
    )

    assert query is not None
    assert query.prefix == "long ha"
    assert query.word_start == text.index("long ha")
    assert query.word_end == len(text)
    assert query.active_tag_end == len(text)


def test_prompt_document_service_autocomplete_query_fails_closed_for_selections_or_mid_segment_cursors() -> (
    None
):
    """Autocomplete queries should fail closed for selections while allowing mid-tag carets."""

    document_service = PromptDocumentService()
    text = "1girl, long hair"
    document_view = document_service.build_document_view(text)

    assert (
        document_service.autocomplete_query_at_cursor(
            document_view,
            text=text,
            cursor_position=len(text),
            has_selection=True,
            minimum_prefix_length=2,
        )
        is None
    )
    query = document_service.autocomplete_query_at_cursor(
        document_view,
        text=text,
        cursor_position=text.index("hair") + len("ha"),
        has_selection=False,
        minimum_prefix_length=2,
    )

    assert query is not None
    assert query.prefix == "long ha"
    assert query.word_start == text.index("long hair")
    assert query.word_end == text.index("hair") + len("ha")
    assert query.active_tag_end == len(text)


def test_prompt_document_service_autocomplete_query_allows_end_of_line_before_later_text() -> (
    None
):
    """Later physical lines should not block autocomplete at the current line end."""

    document_service = PromptDocumentService()
    text = "alpha\nlong ha\nbeta"
    document_view = document_service.build_document_view(text)
    cursor_position = text.index("\nbeta")

    query = document_service.autocomplete_query_at_cursor(
        document_view,
        text=text,
        cursor_position=cursor_position,
        has_selection=False,
        minimum_prefix_length=2,
    )

    assert query is not None
    assert query.prefix == "long ha"
    assert query.word_start == text.index("long ha")
    assert query.word_end == cursor_position
    assert query.active_tag_end == cursor_position


def test_prompt_document_service_autocomplete_query_allows_mid_line_before_text() -> (
    None
):
    """Text ahead on the same physical line should be replaceable at accept time."""

    document_service = PromptDocumentService()
    text = "alpha\nlong hair\nbeta"
    document_view = document_service.build_document_view(text)
    cursor_position = text.index("hair") + len("ha")

    query = document_service.autocomplete_query_at_cursor(
        document_view,
        text=text,
        cursor_position=cursor_position,
        has_selection=False,
        minimum_prefix_length=2,
    )

    assert query is not None
    assert query.prefix == "long ha"
    assert query.word_start == text.index("long hair")
    assert query.word_end == cursor_position
    assert query.active_tag_end == text.index("\nbeta")


def test_prompt_document_service_autocomplete_query_builds_no_comma_suffix_fallback() -> (
    None
):
    """No-comma prompt prose should keep the primary range and expose a suffix fallback."""

    document_service = PromptDocumentService()
    text = "1girl blue ha solo"
    document_view = document_service.build_document_view(text)
    cursor_position = text.index("ha") + len("ha")

    query = document_service.autocomplete_query_at_cursor(
        document_view,
        text=text,
        cursor_position=cursor_position,
        has_selection=False,
        minimum_prefix_length=2,
    )

    assert query is not None
    assert query.prefix == "1girl blue ha"
    assert query.word_start == 0
    assert query.word_end == cursor_position
    assert query.active_tag_end == len(text)
    assert query.fallback_query == PromptAutocompleteFallbackQuery(
        prefix="ha",
        word_start=text.index("ha"),
        word_end=cursor_position,
        active_tag_end=cursor_position,
    )


def test_prompt_document_service_autocomplete_query_uses_emphasis_content_bounds() -> (
    None
):
    """Weighted prompt spans should query content text without entering weight suffixes."""

    document_service = PromptDocumentService()
    text = "(blue ha:1.2), solo"
    document_view = document_service.build_document_view(text)
    cursor_position = text.index("ha") + len("ha")

    query = document_service.autocomplete_query_at_cursor(
        document_view,
        text=text,
        cursor_position=cursor_position,
        has_selection=False,
        minimum_prefix_length=2,
    )
    weight_query = document_service.autocomplete_query_at_cursor(
        document_view,
        text=text,
        cursor_position=text.index("1.") + len("1."),
        has_selection=False,
        minimum_prefix_length=2,
    )

    assert query is not None
    assert query.prefix == "blue ha"
    assert query.word_start == text.index("blue")
    assert query.word_end == cursor_position
    assert query.active_tag_end == cursor_position
    assert weight_query is None


def test_prompt_document_service_autocomplete_query_uses_current_line_visible_start() -> (
    None
):
    """Indented prompt lines should preserve indentation outside the replacement range."""

    document_service = PromptDocumentService()
    text = "alpha\n  long ha\nbeta"
    document_view = document_service.build_document_view(text)
    cursor_position = text.index("\nbeta")

    query = document_service.autocomplete_query_at_cursor(
        document_view,
        text=text,
        cursor_position=cursor_position,
        has_selection=False,
        minimum_prefix_length=2,
    )

    assert query is not None
    assert query.prefix == "long ha"
    assert query.word_start == text.index("long ha")
    assert query.word_end == cursor_position
    assert query.active_tag_end == cursor_position


def test_prompt_document_service_autocomplete_query_allows_whitespace_before_line_break() -> (
    None
):
    """Whitespace after the caret on the same line should not block line-end autocomplete."""

    document_service = PromptDocumentService()
    text = "alpha\nlong ha   \nbeta"
    document_view = document_service.build_document_view(text)
    cursor_position = text.index("   ")

    query = document_service.autocomplete_query_at_cursor(
        document_view,
        text=text,
        cursor_position=cursor_position,
        has_selection=False,
        minimum_prefix_length=2,
    )

    assert query is not None
    assert query.prefix == "long ha"
    assert query.word_start == text.index("long ha")
    assert query.word_end == cursor_position
    assert query.active_tag_end == cursor_position


def test_prompt_document_service_autocomplete_query_ignores_blank_line_without_prefix() -> (
    None
):
    """Blank physical lines should not produce autocomplete queries without typed text."""

    document_service = PromptDocumentService()
    text = "alpha\n\nbeta"
    document_view = document_service.build_document_view(text)

    query = document_service.autocomplete_query_at_cursor(
        document_view,
        text=text,
        cursor_position=text.index("\n\n") + 1,
        has_selection=False,
        minimum_prefix_length=2,
    )

    assert query is None


def test_prompt_document_service_builds_wildcard_query_after_curly_opener() -> None:
    """Typing the curly opener should immediately produce a wildcard query."""

    document_service = PromptDocumentService()

    query = document_service.wildcard_autocomplete_query_at_cursor(
        text="{",
        cursor_position=1,
        has_selection=False,
    )

    assert query is not None
    assert query.prefix == ""
    assert query.opener_start == 0
    assert query.replacement_end == 1


def test_prompt_document_service_builds_scene_query_after_line_start_marker() -> None:
    """Typing a line-start scene marker should produce a scene title query."""

    document_service = PromptDocumentService()
    text = "quality\n  **por"

    query = document_service.scene_autocomplete_query_at_cursor(
        text=text,
        cursor_position=len(text),
        has_selection=False,
    )

    assert query is not None
    assert query.prefix == "por"
    assert query.marker_start == text.index("**")
    assert query.title_start == text.index("por")
    assert query.replacement_end == len(text)


def test_prompt_document_service_scene_query_requires_line_start_marker() -> None:
    """Scene autocomplete should not trigger for inline marker text."""

    document_service = PromptDocumentService()

    inline_query = document_service.scene_autocomplete_query_at_cursor(
        text="quality **por",
        cursor_position=len("quality **por"),
        has_selection=False,
    )
    legacy_query = document_service.scene_autocomplete_query_at_cursor(
        text="@por",
        cursor_position=len("@por"),
        has_selection=False,
    )

    assert inline_query is None
    assert legacy_query is None


def test_prompt_document_service_wildcard_query_replaces_existing_closer() -> None:
    """Wildcard completion should own the existing placeholder shell when present."""

    document_service = PromptDocumentService()
    text = "{ani}"

    query = document_service.wildcard_autocomplete_query_at_cursor(
        text=text,
        cursor_position=text.index("}"),
        has_selection=False,
    )

    assert query is not None
    assert query.prefix == "ani"
    assert query.replacement_end == len(text)


def test_autocomplete_replacement_text_formats_prompt_safe_inserted_tag_text() -> None:
    """Autocomplete replacement text should normalize booru tags into prompt-safe text."""

    assert autocomplete_replacement_text("looking_at_viewer") == "looking at viewer"
    assert autocomplete_replacement_text("cat_(animal)") == r"cat \(animal\)"


def test_filter_noop_autocomplete_suggestions_drops_semantically_identical_tags() -> (
    None
):
    """Autocomplete should suppress suggestions that already match the current prompt slice."""

    query = PromptAutocompleteQuery(
        prefix="looking at viewer",
        word_start=0,
        word_end=17,
        active_tag_end=17,
    )
    suggestions = (
        PromptAutocompleteSuggestion("looking_at_viewer", 100),
        PromptAutocompleteSuggestion("looking_away", 50),
    )

    filtered_suggestions = filter_noop_autocomplete_suggestions(
        text="looking at viewer",
        query=query,
        suggestions=suggestions,
    )

    assert filtered_suggestions == (PromptAutocompleteSuggestion("looking_away", 50),)


def test_filter_noop_autocomplete_suggestions_keeps_partial_completions() -> None:
    """Autocomplete should keep suggestions that extend the current prompt slice."""

    query = PromptAutocompleteQuery(
        prefix="looking at vi",
        word_start=0,
        word_end=13,
        active_tag_end=13,
    )
    suggestions = (PromptAutocompleteSuggestion("looking_at_viewer", 100),)

    filtered_suggestions = filter_noop_autocomplete_suggestions(
        text="looking at vi",
        query=query,
        suggestions=suggestions,
    )

    assert filtered_suggestions == suggestions

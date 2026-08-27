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

"""Test wildcard document autocomplete mapping."""

from __future__ import annotations


from substitute.application.managed_text_assets.wildcard_csv_document_semantics import (
    WildcardCsvDocumentSemantics,
)
from substitute.application.managed_text_assets.wildcard_text_document_semantics import (
    WildcardTextDocumentSemantics,
)
from substitute.application.prompt_editor.autocomplete.query_service import (
    PromptAutocompleteQueryService,
)
from substitute.application.prompt_editor.document.service import PromptDocumentService


def test_wildcard_autocomplete_never_creates_scene_queries() -> None:
    """Scene autocomplete should be absent under wildcard document semantics."""

    service = PromptAutocompleteQueryService(
        document_semantics=WildcardTextDocumentSemantics()
    )

    query = service.scene_autocomplete_query_at_cursor(
        text="**por",
        cursor_position=5,
        has_selection=False,
    )

    assert query is None


def test_txt_wildcard_autocomplete_matches_ordinary_non_scene_queries() -> None:
    """TXT wildcard boundaries should not isolate normal autocomplete queries."""

    source = "blue_ha\n{ani\n<lora:mod"
    document_view = PromptDocumentService().build_document_view(source)
    ordinary = PromptAutocompleteQueryService()
    wildcard = PromptAutocompleteQueryService(
        document_semantics=WildcardTextDocumentSemantics()
    )

    assert wildcard.autocomplete_query_at_cursor(
        document_view,
        text=source,
        cursor_position=len("blue_ha"),
        has_selection=False,
        minimum_prefix_length=1,
    ) == ordinary.autocomplete_query_at_cursor(
        document_view,
        text=source,
        cursor_position=len("blue_ha"),
        has_selection=False,
        minimum_prefix_length=1,
    )
    wildcard_position = source.index("{ani") + len("{ani")
    assert wildcard.wildcard_autocomplete_query_at_cursor(
        text=source,
        cursor_position=wildcard_position,
        has_selection=False,
    ) == ordinary.wildcard_autocomplete_query_at_cursor(
        text=source,
        cursor_position=wildcard_position,
        has_selection=False,
    )
    lora_position = len(source)
    assert wildcard.lora_autocomplete_query_at_cursor(
        text=source,
        cursor_position=lora_position,
        has_selection=False,
    ) == ordinary.lora_autocomplete_query_at_cursor(
        text=source,
        cursor_position=lora_position,
        has_selection=False,
    )


def test_csv_autocomplete_protects_headers_and_reads_decoded_values() -> None:
    """CSV autocomplete should operate on values without editing structure."""

    source = "Name,{Head\nfox,{ani"
    service = PromptAutocompleteQueryService(
        document_semantics=WildcardCsvDocumentSemantics()
    )

    header_query = service.wildcard_autocomplete_query_at_cursor(
        text=source,
        cursor_position=len("Name,{Head"),
        has_selection=False,
    )
    data_query = service.wildcard_autocomplete_query_at_cursor(
        text=source,
        cursor_position=len(source),
        has_selection=False,
    )

    assert header_query is None
    assert data_query is not None
    assert data_query.prefix == "ani"
    assert data_query.opener_start == source.rindex("{")


def test_csv_plain_autocomplete_decodes_quoted_values_and_maps_ranges() -> None:
    """Plain tag autocomplete should behave normally inside quoted CSV values."""

    source = 'Prompt\n"blue_ha, other"'
    value_start = source.index("blue_ha")
    cursor_position = value_start + len("blue_ha")
    service = PromptAutocompleteQueryService(
        document_semantics=WildcardCsvDocumentSemantics()
    )

    query = service.autocomplete_query_at_cursor(
        PromptDocumentService().build_document_view(source),
        text=source,
        cursor_position=cursor_position,
        has_selection=False,
        minimum_prefix_length=1,
    )

    assert query is not None
    assert query.prefix == "blue_ha"
    assert query.word_start == value_start
    assert query.word_end == cursor_position
    assert source[query.word_start : query.active_tag_end] == "blue_ha"


def test_csv_lora_autocomplete_decodes_escaped_quotes_and_maps_ranges() -> None:
    """LoRA autocomplete should ignore CSV encoding while preserving raw ranges."""

    source = 'Prompt\n"detail ""quoted"", <lora:mod"'
    cursor_position = source.index("mod") + len("mod")
    service = PromptAutocompleteQueryService(
        document_semantics=WildcardCsvDocumentSemantics()
    )

    query = service.lora_autocomplete_query_at_cursor(
        text=source,
        cursor_position=cursor_position,
        has_selection=False,
    )

    assert query is not None
    assert query.query_text == "mod"
    assert source[query.replacement_start : query.replacement_end] == "<lora:mod"

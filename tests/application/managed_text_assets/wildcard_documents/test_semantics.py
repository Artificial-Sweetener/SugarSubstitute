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

"""Test wildcard TXT and CSV document semantics."""

from __future__ import annotations


from substitute.application.managed_text_assets.wildcard_csv_document_parser import (
    parse_wildcard_csv_document,
)
from substitute.application.managed_text_assets.wildcard_csv_document_semantics import (
    WildcardCsvDocumentSemantics,
)
from substitute.application.managed_text_assets.wildcard_text_document_semantics import (
    WildcardTextDocumentSemantics,
)
from substitute.application.prompt_editor.document.semantics import (
    OrdinaryPromptDocumentSemantics,
)


def test_ordinary_prompt_semantics_preserve_one_scene_capable_value() -> None:
    """Ordinary prompt semantics should preserve the existing whole prompt value."""

    semantics = OrdinaryPromptDocumentSemantics()

    mappings = semantics.value_mappings_for_text("first\n**Scene")

    assert semantics.scenes_enabled is True
    assert semantics.prompt_content_text("first\n**Scene") == "first\n**Scene"
    assert tuple(mapping.logical_text for mapping in mappings) == ("first\n**Scene",)
    assert semantics.unsupported_scene_marker_ranges("**Scene") == ()


def test_txt_wildcard_semantics_map_non_empty_candidate_lines() -> None:
    """TXT candidates should expose trimmed prompt-value mappings."""

    source = "  first, tag  \r\n\r\nsecond, tag\n"
    semantics = WildcardTextDocumentSemantics()

    mappings = semantics.value_mappings_for_text(source)

    assert semantics.scenes_enabled is False
    assert tuple(mapping.logical_text for mapping in mappings) == (
        "first, tag",
        "second, tag",
    )
    assert tuple(
        source[mapping.source_range.start : mapping.source_range.end]
        for mapping in mappings
    ) == ("first, tag", "second, tag")
    assert semantics.prompt_content_text(source) == source


def test_txt_wildcard_semantics_report_only_leading_scene_markers() -> None:
    """TXT validation should flag candidate-leading markers but not later stars."""

    source = "  **Scene\nstars ** glitter\n***Scene\n"

    marker_ranges = WildcardTextDocumentSemantics().unsupported_scene_marker_ranges(
        source
    )

    assert tuple(source[item.start : item.end] for item in marker_ranges) == (
        "**",
        "**",
    )
    assert tuple(item.start for item in marker_ranges) == (2, source.index("***Scene"))


def test_csv_parser_maps_quoted_commas_quotes_and_multiline_cells() -> None:
    """CSV parsing should retain exact ranges for decoded structured values."""

    source = 'Name,Prompt\r\nfox,"red, ""bright""\nforest"\r\nwolf,plain'

    document = parse_wildcard_csv_document(source)

    assert document.valid is True
    assert tuple(cell.value for cell in document.records[1]) == (
        "fox",
        'red, "bright"\nforest',
    )
    prompt_cell = document.records[1][1]
    assert source[prompt_cell.source_range.start] == '"'
    quote_index = prompt_cell.value.index('"')
    quote_range = prompt_cell.value_character_ranges[quote_index]
    assert source[quote_range.start : quote_range.end] == '""'


def test_csv_wildcard_semantics_exclude_headers_and_map_data_cells() -> None:
    """CSV mappings should include trimmed data cells without header values."""

    source = 'Name,Prompt\nfox,"  blue hair, green eyes  "\nwolf,red hair'

    mappings = WildcardCsvDocumentSemantics().value_mappings_for_text(source)

    assert tuple(mapping.logical_text for mapping in mappings) == (
        "fox",
        "blue hair, green eyes",
        "wolf",
        "red hair",
    )
    prompt_mapping = mappings[1]
    assert (
        source[prompt_mapping.source_range.start : prompt_mapping.source_range.end]
        == "blue hair, green eyes"
    )
    assert WildcardCsvDocumentSemantics().prompt_content_text(source) == (
        "fox\nblue hair, green eyes\nwolf\nred hair"
    )


def test_csv_wildcard_semantics_map_empty_data_cells_to_safe_anchors() -> None:
    """Empty CSV data cells should remain writable values without exposing headers."""

    source = 'First,Second\n,""'
    semantics = WildcardCsvDocumentSemantics()
    mappings = semantics.value_mappings_for_text(source)

    assert tuple(mapping.logical_text for mapping in mappings) == ("", "")
    assert tuple(mapping.source_range.start for mapping in mappings) == (
        source.index("\n") + 1,
        source.rindex('"'),
    )
    updated = semantics.replace_value_text(source, mappings[1].value_id, "value")
    assert updated == 'First,Second\n,"value"'


def test_csv_wildcard_semantics_find_markers_in_independent_cells() -> None:
    """CSV validation should find markers at decoded data-cell starts."""

    source = 'Name,Prompt\nfox," **Scene, forest"\nwolf,stars ** glitter'

    marker_ranges = WildcardCsvDocumentSemantics().unsupported_scene_marker_ranges(
        source
    )

    assert tuple(source[item.start : item.end] for item in marker_ranges) == ("**",)


def test_csv_wildcard_semantics_fail_closed_for_unclosed_quotes() -> None:
    """Malformed quoted CSV should expose no ambiguous prompt values."""

    semantics = WildcardCsvDocumentSemantics()

    assert semantics.value_mappings_for_text('Name,Prompt\nfox,"unclosed') == ()
    assert semantics.unsupported_scene_marker_ranges('Name,Prompt\nfox,"**Scene') == ()

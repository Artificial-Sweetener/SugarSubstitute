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

"""Tests for text-authored prompt scene parsing."""

from __future__ import annotations

from substitute.domain.prompt import (
    materialize_scene_prompt,
    normalize_scene_title,
    parse_prompt_scene_document,
    scene_block_at_source_position,
)


def test_scene_parser_treats_unmarked_prompt_as_universal() -> None:
    """A prompt without scene markers should be universal for every scene."""

    document = parse_prompt_scene_document("quality, {character}")

    assert document.has_scenes is False
    assert document.universal_text == "quality, {character}"
    assert document.scenes == ()


def test_scene_parser_splits_universal_text_and_scene_blocks() -> None:
    """Line-start scene markers should split universal and scene-local prompt text."""

    source = "quality\n\n**portrait\nstudio portrait\n\n**cafe\nsitting in cafe"

    document = parse_prompt_scene_document(source)

    assert document.universal_text == "quality\n\n"
    assert [scene.marker.title for scene in document.scenes] == ["portrait", "cafe"]
    assert [scene.marker.normalized_key for scene in document.scenes] == [
        "portrait",
        "cafe",
    ]
    assert document.scenes[0].text == "studio portrait\n\n"
    assert document.scenes[1].text == "sitting in cafe"


def test_scene_parser_allows_prompt_to_start_with_scene() -> None:
    """A prompt can omit universal text and begin with its first scene marker."""

    document = parse_prompt_scene_document("**portrait\nstudio portrait")

    assert document.universal_text == ""
    assert document.scenes[0].marker.title == "portrait"
    assert document.scenes[0].text == "studio portrait"


def test_scene_parser_accepts_indented_markers_and_preserves_title_range() -> None:
    """Leading indentation should not prevent scene marker recognition."""

    source = "  **Cafe   Interior  \r\nwarm light"

    document = parse_prompt_scene_document(source)
    marker = document.scenes[0].marker

    assert marker.title == "Cafe   Interior"
    assert marker.normalized_key == "cafe interior"
    assert marker.marker_range.slice(source) == "**"
    assert marker.title_range.slice(source) == "Cafe   Interior"
    assert document.scenes[0].text == "warm light"


def test_scene_parser_ignores_inline_legacy_at_and_empty_markers() -> None:
    """Only non-empty line-start markers should declare prompt scenes."""

    source = (
        "email@example.com\nquality **portrait\n*\n**\n**   \n@portrait\n**valid\ntext"
    )

    document = parse_prompt_scene_document(source)

    assert (
        document.universal_text
        == "email@example.com\nquality **portrait\n*\n**\n**   \n@portrait\n"
    )
    assert [scene.marker.title for scene in document.scenes] == ["valid"]


def test_scene_parser_marks_duplicate_scene_markers() -> None:
    """Duplicate normalized scene keys should be flagged after the first marker."""

    document = parse_prompt_scene_document(
        "**Cafe   Interior\none\n**cafe interior\ntwo",
    )

    assert document.scenes[0].marker.duplicate is False
    assert document.scenes[1].marker.duplicate is True
    assert document.first_scene_for_key("cafe interior") is document.scenes[0]


def test_scene_prompt_materialization_joins_universal_and_scene_text() -> None:
    """Universal and scene-local prompt text should join with a blank line."""

    assert (
        materialize_scene_prompt(universal_text="quality\n", scene_text="\nportrait ")
        == "quality\n\nportrait"
    )
    assert (
        materialize_scene_prompt(universal_text="quality", scene_text="") == "quality"
    )
    assert materialize_scene_prompt(universal_text="", scene_text="portrait") == (
        "portrait"
    )
    assert normalize_scene_title(" Cafe   Interior ") == "cafe interior"


def test_scene_lookup_returns_none_outside_scene_blocks() -> None:
    """Scene source-position lookup should ignore universal-only text."""

    unmarked_document = parse_prompt_scene_document("quality")
    scene_document = parse_prompt_scene_document("quality\n\n**portrait\nportrait")

    assert scene_block_at_source_position(unmarked_document, 0) is None
    assert scene_block_at_source_position(scene_document, 0) is None
    assert scene_block_at_source_position(scene_document, len("quality\n")) is None


def test_scene_lookup_resolves_marker_line_and_content_positions() -> None:
    """Scene lookup should cover indentation, marker, title, newline, and content."""

    source = "quality\n  **Cafe   Interior  \r\nwarm light"
    document = parse_prompt_scene_document(source)
    scene = document.scenes[0]

    assert scene_block_at_source_position(document, source.index("  **")) is scene
    assert scene_block_at_source_position(document, source.index("**")) is scene
    assert scene_block_at_source_position(document, source.index("Cafe")) is scene
    assert scene_block_at_source_position(document, source.index("\r\n") + 1) is scene
    assert scene_block_at_source_position(document, source.index("warm")) is scene


def test_scene_lookup_respects_scene_boundaries_and_duplicates() -> None:
    """Scene lookup should return the block owning the clicked source boundary."""

    source = "**portrait\none\n**cafe\ntwo\n**Portrait\nthree"
    document = parse_prompt_scene_document(source)

    first_scene = document.scenes[0]
    second_scene = document.scenes[1]
    duplicate_scene = document.scenes[2]

    assert scene_block_at_source_position(document, source.index("one")) is first_scene
    assert (
        scene_block_at_source_position(document, source.index("**cafe")) is second_scene
    )
    assert scene_block_at_source_position(document, source.index("two")) is second_scene
    assert (
        scene_block_at_source_position(document, source.rindex("**Portrait"))
        is duplicate_scene
    )
    assert duplicate_scene.marker.duplicate is True


def test_scene_lookup_resolves_final_document_boundary_to_last_scene() -> None:
    """Scene lookup should allow editor hit testing at the end of the final scene."""

    source = "quality\n**portrait\nportrait"
    document = parse_prompt_scene_document(source)

    assert scene_block_at_source_position(document, len(source)) is document.scenes[0]
    assert (
        scene_block_at_source_position(document, len(source) + 10)
        is (document.scenes[0])
    )


def test_scene_parser_treats_legacy_at_marker_as_prompt_text() -> None:
    """Legacy at-sign marker text should no longer declare prompt scenes."""

    source = "@portrait\ntext"

    document = parse_prompt_scene_document(source)

    assert document.has_scenes is False
    assert document.universal_text == source

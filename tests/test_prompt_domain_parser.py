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

"""Pure parser tests for the prompt-domain model."""

from __future__ import annotations

from decimal import Decimal

from substitute.domain.prompt import WildcardForm, parse_prompt_document
from substitute.domain.prompt import PromptWildcardSyntaxProfile


def test_parse_prompt_document_splits_top_level_segments_and_ranges() -> None:
    """Top-level commas should split segments while separator ranges keep trailing spaces."""

    document = parse_prompt_document("alpha, beta, gamma")

    assert [segment.text for segment in document.segments] == ["alpha", "beta", "gamma"]
    assert document.segments[0].content_range == document.segments[0].visible_range
    assert document.segments[0].separator_range is not None
    assert (
        document.segments[0].separator_range.start,
        document.segments[0].separator_range.end,
    ) == (5, 7)
    assert (
        document.segments[1].content_range.start,
        document.segments[1].content_range.end,
    ) == (7, 11)


def test_parse_prompt_document_ignores_commas_inside_quotes_and_brackets() -> None:
    """Quotes and nested bracket groups should suppress top-level segment splitting."""

    document = parse_prompt_document('a, "b,c", (d,e), f')

    assert [segment.text for segment in document.segments] == [
        "a",
        '"b,c"',
        "(d,e)",
        "f",
    ]


def test_parse_prompt_document_ignores_commas_inside_single_quoted_text() -> None:
    """Single quoted text should keep comma splitting suppressed."""

    document = parse_prompt_document("a, 'b,c', d")

    assert [segment.text for segment in document.segments] == ["a", "'b,c'", "d"]


def test_parse_prompt_document_treats_curly_brace_groups_like_other_brackets() -> None:
    """Balanced brace groups should suppress top-level segment splitting like other brackets."""

    document = parse_prompt_document("alpha, {beta, gamma}, delta")

    assert [segment.text for segment in document.segments] == [
        "alpha",
        "{beta, gamma}",
        "delta",
    ]


def test_parse_prompt_document_tracks_nested_emphasis_ranges_and_depths() -> None:
    """Nested weighted prompts should produce stable outer, content, and weight ranges."""

    document = parse_prompt_document("((cat:1.2) dog:1.1)")

    assert len(document.emphasis_spans) == 2
    outer_span, inner_span = document.emphasis_spans
    assert (
        outer_span.outer_range.start,
        outer_span.outer_range.end,
        outer_span.content_range.start,
        outer_span.content_range.end,
        outer_span.weight_range.start,
        outer_span.weight_range.end,
        outer_span.weight,
        outer_span.depth,
    ) == (0, 19, 1, 14, 15, 18, Decimal("1.1"), 0)
    assert (
        inner_span.outer_range.start,
        inner_span.outer_range.end,
        inner_span.content_range.start,
        inner_span.content_range.end,
        inner_span.weight_range.start,
        inner_span.weight_range.end,
        inner_span.weight,
        inner_span.depth,
    ) == (1, 10, 2, 5, 6, 9, Decimal("1.2"), 1)


def test_parse_prompt_document_tracks_simple_wildcard_spans() -> None:
    """Simple wildcard placeholders should produce normalized wildcard spans and syntax spans."""

    document = parse_prompt_document("alpha, {pokemon/gen1/types}, beta")

    assert len(document.wildcard_spans) == 1
    wildcard = document.wildcard_spans[0]
    assert (
        wildcard.outer_range.start,
        wildcard.outer_range.end,
        wildcard.content_range.start,
        wildcard.content_range.end,
        wildcard.wildcard_form,
        wildcard.identifier,
        wildcard.csv_column,
        wildcard.depth,
    ) == (7, 27, 8, 26, WildcardForm.SIMPLE, "pokemon/gen1/types", None, 0)
    assert [
        (span.kind.value, span.source_range.start, span.source_range.end)
        for span in document.syntax_spans
    ] == [("wildcard", 7, 27)]


def test_parse_prompt_document_tracks_csv_wildcard_spans() -> None:
    """CSV wildcard placeholders should keep the normalized identifier and column name."""

    document = parse_prompt_document("{csv:pokemon/gen1/moves:effect}, next")

    assert len(document.wildcard_spans) == 1
    wildcard = document.wildcard_spans[0]
    assert (
        wildcard.outer_range.start,
        wildcard.outer_range.end,
        wildcard.content_range.start,
        wildcard.content_range.end,
        wildcard.wildcard_form,
        wildcard.identifier,
        wildcard.csv_column,
    ) == (
        0,
        31,
        1,
        30,
        WildcardForm.CSV,
        "pokemon/gen1/moves",
        "effect",
    )


def test_parse_prompt_document_tracks_curly_wildcard_tags() -> None:
    """Wildcard tags should be parsed separately from the source identifier."""

    document = parse_prompt_document("{animal|variant}, {csv:monster:color|alt}")

    assert [
        (span.identifier, span.csv_column, span.tag) for span in document.wildcard_spans
    ] == [
        ("animal", None, "variant"),
        ("monster", "color", "alt"),
    ]


def test_parse_prompt_document_tracks_double_underscore_wildcards() -> None:
    """Configured double-underscore activators should produce wildcard spans."""

    document = parse_prompt_document(
        "__animal__, __csv:monster:color__",
        wildcard_syntax_profile=PromptWildcardSyntaxProfile.double_underscore(),
    )

    assert [
        (span.wildcard_form, span.identifier, span.csv_column)
        for span in document.wildcard_spans
    ] == [
        (WildcardForm.SIMPLE, "animal", None),
        (WildcardForm.CSV, "monster", "color"),
    ]


def test_parse_prompt_document_custom_profile_can_disable_curly_compatibility() -> None:
    """Custom profiles should honor the explicit curly compatibility switch."""

    profile = PromptWildcardSyntaxProfile.custom(
        prefix="%%",
        suffix="%%",
        also_recognize_curly=False,
    )
    document = parse_prompt_document(
        "%%animal%%, {animal}",
        wildcard_syntax_profile=profile,
    )

    assert [
        (span.identifier, span.outer_range.start) for span in document.wildcard_spans
    ] == [("animal", 0)]


def test_parse_prompt_document_treats_malformed_emphasis_as_plain_text() -> None:
    """Malformed weights should not raise and should not create emphasis spans."""

    document = parse_prompt_document("(cat:abc), plain")

    assert document.emphasis_spans == ()
    assert [segment.text for segment in document.segments] == ["(cat:abc)", "plain"]


def test_parse_prompt_document_treats_invalid_wildcards_as_plain_text() -> None:
    """Malformed wildcard placeholders should not raise and should not create wildcard spans."""

    malformed_examples = (
        "{ }",
        "{ csv:monster:color}",
        "{csv:monster}",
        "{csv:monster: }",
        "{monster\\types}",
        "{monster:{color}}",
        "{csv:monster:color:extra}",
    )

    for text in malformed_examples:
        document = parse_prompt_document(f"{text}, plain")

        assert document.wildcard_spans == ()
        assert [segment.text for segment in document.segments] == [text, "plain"]


def test_parse_prompt_document_preserves_emphasis_and_wildcards_together() -> None:
    """Emphasis and wildcard spans should coexist in one deterministic syntax span list."""

    document = parse_prompt_document("({animal}:1.05), {csv:monster:color}")

    assert len(document.emphasis_spans) == 1
    assert len(document.wildcard_spans) == 2
    assert [
        (span.kind.value, span.source_range.start, span.source_range.end, span.depth)
        for span in document.syntax_spans
    ] == [
        ("emphasis", 0, 15, 0),
        ("wildcard", 1, 9, 0),
        ("wildcard", 17, 36, 0),
    ]


def test_parse_prompt_document_tracks_lora_schedule_spans() -> None:
    """LoRA schedule tokens should expose path and weight source ranges."""

    document = parse_prompt_document(r"<lora:Illustrious\Character\Mineru:0.8>")

    assert len(document.lora_spans) == 1
    lora = document.lora_spans[0]
    assert (
        lora.outer_range.start,
        lora.outer_range.end,
        lora.name_range.slice(document.source_text),
        lora.first_weight_range.slice(document.source_text),
        lora.first_weight,
        lora.second_weight,
    ) == (
        0,
        len(document.source_text),
        r"Illustrious\Character\Mineru",
        "0.8",
        Decimal("0.8"),
        None,
    )
    assert [
        (span.kind.value, span.source_range.start, span.source_range.end)
        for span in document.syntax_spans
    ] == [("lora", 0, len(document.source_text))]


def test_parse_prompt_document_treats_lora_apostrophes_as_filename_text() -> None:
    """LoRA schedule names should allow apostrophes used by real model files."""

    document = parse_prompt_document(
        r"<lora:Anima\style\People'sWorks_v10_Animabasev1.0_test3-000008:1.00>"
    )

    assert len(document.lora_spans) == 1
    lora = document.lora_spans[0]
    assert (
        lora.name_range.slice(document.source_text),
        lora.first_weight_range.slice(document.source_text),
        lora.first_weight,
    ) == (
        r"Anima\style\People'sWorks_v10_Animabasev1.0_test3-000008",
        "1.00",
        Decimal("1.00"),
    )


def test_parse_prompt_document_treats_word_apostrophes_as_plain_text_before_loras() -> (
    None
):
    """Word apostrophes before LoRA tags should not hide later LoRA schedule spans."""

    text = (
        "grabbing another's breast, "
        r"<lora:styles\first:1.00> <lora:characters\second:0.75> "
        "<lora:third:1>"
    )

    document = parse_prompt_document(text)

    assert [span.name_range.slice(text) for span in document.lora_spans] == [
        r"styles\first",
        r"characters\second",
        "third",
    ]
    assert [span.first_weight_range.slice(text) for span in document.lora_spans] == [
        "1.00",
        "0.75",
        "1",
    ]


def test_parse_prompt_document_tracks_two_weight_lora_schedule_spans() -> None:
    """LoRA schedule tokens should tolerate Prompt Control two-weight syntax."""

    document = parse_prompt_document("<lora:Mineru:0.8:0.6>")

    assert len(document.lora_spans) == 1
    lora = document.lora_spans[0]
    assert lora.first_weight == Decimal("0.8")
    assert lora.second_weight == Decimal("0.6")
    assert lora.second_weight_range is not None
    assert lora.second_weight_range.slice(document.source_text) == "0.6"


def test_parse_prompt_document_treats_invalid_lora_tokens_as_plain_text() -> None:
    """Malformed LoRA tokens should not create LoRA spans."""

    malformed_examples = (
        "<lora:bad:name:0.8>",
        "<lora:Mineru>",
        "<lora::0.8>",
        "<lora:Mineru:abc>",
    )

    for text in malformed_examples:
        document = parse_prompt_document(f"{text}, plain")

        assert document.lora_spans == ()
        assert [segment.text for segment in document.segments] == [text, "plain"]


def test_parse_prompt_document_tolerates_incomplete_quotes_and_brackets() -> None:
    """Unclosed quote and bracket constructs should remain parseable."""

    incomplete_quote = parse_prompt_document('alpha, "beta,gamma')
    incomplete_bracket = parse_prompt_document("alpha, (beta,gamma")

    assert [segment.text for segment in incomplete_quote.segments] == [
        "alpha",
        '"beta,gamma',
    ]
    assert [segment.text for segment in incomplete_bracket.segments] == [
        "alpha",
        "(beta,gamma",
    ]


def test_parse_prompt_document_treats_unterminated_wildcards_as_plain_text() -> None:
    """Unterminated brace groups should remain plain text and continue segmenting safely."""

    document = parse_prompt_document("alpha, {monster,color")

    assert document.wildcard_spans == ()
    assert [segment.text for segment in document.segments] == [
        "alpha",
        "{monster,color",
    ]


def test_parse_prompt_document_tracks_trailing_comma_without_fake_segment() -> None:
    """Trailing comma intent should live on document metadata, not an empty segment."""

    document = parse_prompt_document("alpha, beta, ")

    assert document.has_trailing_comma is True
    assert [segment.text for segment in document.segments] == ["alpha", "beta"]


def test_parse_prompt_document_treats_escaped_parentheses_as_literal_text() -> None:
    """Escaped parentheses should stay plain and must not create emphasis spans."""

    document = parse_prompt_document(r"painting \(medium\)")

    assert document.emphasis_spans == ()
    assert [segment.text for segment in document.segments] == [r"painting \(medium\)"]


def test_parse_prompt_document_treats_escaped_weight_shape_as_literal_text() -> None:
    """Escaped weighted-looking groups should stay literal instead of parsing as emphasis."""

    document = parse_prompt_document(r"\(painting:1.2\)")

    assert document.emphasis_spans == ()
    assert [segment.text for segment in document.segments] == [r"\(painting:1.2\)"]


def test_parse_prompt_document_keeps_dataset_colon_number_tags_literal_when_escaped() -> (
    None
):
    """Dataset-style parenthetical tags with colon-number text should remain plain."""

    document = parse_prompt_document(r"vertin \(reverse:1999\)")

    assert document.emphasis_spans == ()
    assert [segment.text for segment in document.segments] == [
        r"vertin \(reverse:1999\)"
    ]


def test_parse_prompt_document_ignores_commas_inside_balanced_escaped_parentheses() -> (
    None
):
    """Balanced escaped literal parens should still suppress top-level comma splitting."""

    document = parse_prompt_document(r"alpha, painting \(medium, oil\), beta")

    assert [segment.text for segment in document.segments] == [
        "alpha",
        r"painting \(medium, oil\)",
        "beta",
    ]

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

"""Keep word punctuation from suppressing later prompt syntax and editing."""

from decimal import Decimal

import pytest

from substitute.domain.prompt.document.parser import parse_prompt_document
from substitute.domain.prompt.document.structural_scan import balanced_parenthesis_pairs


@pytest.mark.parametrize(
    "phrase",
    (
        "jack-o' challenge",
        "girls' outfits",
        "artists' work",
        "café' portrait",
        "another's portrait",
    ),
)
def test_word_apostrophes_preserve_following_prompt_syntax(phrase: str) -> None:
    """Recognize LoRAs and signed weights after trailing or internal apostrophes."""
    text = rf"(before:1.21), {phrase}, <lora:ANIMA\retro:1.00>, (after:-1.00)"

    document = parse_prompt_document(text)

    assert document.source_text == text
    assert [span.name_range.slice(text) for span in document.lora_spans] == [
        r"ANIMA\retro"
    ]
    assert [span.weight for span in document.emphasis_spans] == [
        Decimal("1.21"),
        Decimal("-1.00"),
    ]
    assert [segment.text for segment in document.segments] == [
        "(before:1.21)",
        phrase,
        r"<lora:ANIMA\retro:1.00>",
        "(after:-1.00)",
    ]
    pairs = balanced_parenthesis_pairs(text)
    assert [text[pair.opening_index : pair.closing_index + 1] for pair in pairs] == [
        "(before:1.21)",
        "(after:-1.00)",
    ]


@pytest.mark.parametrize("quoted", ("'cat, dog'", '"cat, dog"', "'don't, change'"))
def test_quoted_phrases_keep_delimiters_and_close_before_loras(quoted: str) -> None:
    """Preserve intentional quoted phrases and contractions inside those phrases."""
    text = rf"portrait, {quoted}, <lora:styles\retro:0.80>, (after:1.20)"

    document = parse_prompt_document(text)

    assert [segment.text for segment in document.segments] == [
        "portrait",
        quoted,
        r"<lora:styles\retro:0.80>",
        "(after:1.20)",
    ]
    assert len(document.lora_spans) == 1
    assert len(document.emphasis_spans) == 1


def test_unclosed_quoted_phrase_still_suppresses_its_contents() -> None:
    """Retain tolerant incomplete quoted-text behavior during ordinary typing."""
    text = "portrait, 'unclosed, (literal:1.20)"

    document = parse_prompt_document(text)

    assert [segment.text for segment in document.segments] == [
        "portrait",
        "'unclosed, (literal:1.20)",
    ]
    assert document.emphasis_spans == ()
    assert balanced_parenthesis_pairs(text) == ()

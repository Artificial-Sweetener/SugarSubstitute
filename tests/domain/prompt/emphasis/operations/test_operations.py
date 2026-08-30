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

"""Pure mutation tests for prompt-domain operations."""

from __future__ import annotations

from decimal import Decimal


from substitute.domain.prompt.document.ranges import SourceRange
from substitute.domain.prompt.document.parser import parse_prompt_document
from substitute.domain.prompt.emphasis.operations import (
    decrease_emphasis,
    increase_emphasis,
    replace_span_content,
    set_emphasis_weight,
)


def test_increase_emphasis_wraps_plain_selection_with_default_weight() -> None:
    """Plain text selections should wrap into a new weighted emphasis span."""

    document = parse_prompt_document("cat")

    result = increase_emphasis(document, SourceRange(0, 3))

    assert result.text == "(cat:1.05)"
    assert result.selection_range is not None
    assert (result.selection_range.start, result.selection_range.end) == (1, 4)


def test_increase_emphasis_updates_existing_weight_in_place() -> None:
    """Existing emphasis should keep its content and update only its numeric weight."""

    document = parse_prompt_document("(cat:1.05)")

    result = increase_emphasis(document, document.emphasis_spans[0].content_range)

    assert result.text == "(cat:1.10)"
    assert result.selection_range == document.emphasis_spans[0].content_range


def test_decrease_emphasis_updates_existing_weight_in_place() -> None:
    """Existing emphasis should decrease its weight deterministically."""

    document = parse_prompt_document("(cat:1.20)")

    result = decrease_emphasis(document, document.emphasis_spans[0].content_range)

    assert result.text == "(cat:1.15)"
    assert result.selection_range == document.emphasis_spans[0].content_range


def test_decrease_emphasis_crosses_zero_into_negative_weight() -> None:
    """Decreasing zero emphasis should produce the next signed weight step."""

    document = parse_prompt_document("(cat:0.00)")

    result = decrease_emphasis(document, document.emphasis_spans[0].content_range)

    assert result.text == "(cat:-0.05)"
    assert result.document.emphasis_spans[0].weight == Decimal("-0.05")
    assert result.selection_range == document.emphasis_spans[0].content_range


def test_increase_emphasis_crosses_negative_weight_back_to_zero() -> None:
    """Increasing negative emphasis should cross back through zero exactly."""

    document = parse_prompt_document("(cat:-0.05)")

    result = increase_emphasis(document, document.emphasis_spans[0].content_range)

    assert result.text == "(cat:0.00)"
    assert result.document.emphasis_spans[0].weight == Decimal("0.00")
    assert result.selection_range == document.emphasis_spans[0].content_range


def test_decrease_emphasis_unwraps_when_weight_returns_to_neutral() -> None:
    """Neutral emphasis should remove the wrapping shell entirely."""

    document = parse_prompt_document("(cat:1.05)")

    result = decrease_emphasis(document, document.emphasis_spans[0].content_range)

    assert result.text == "cat"
    assert result.selection_range is not None
    assert (result.selection_range.start, result.selection_range.end) == (0, 3)


def test_increase_emphasis_updates_only_inner_nested_span() -> None:
    """Nested emphasis adjustments should target only the requested inner shell."""

    document = parse_prompt_document("((cat:1.20) dog:1.10)")
    inner_span = document.emphasis_spans[1]

    result = increase_emphasis(document, inner_span.content_range)

    assert result.text == "((cat:1.25) dog:1.10)"
    assert result.selection_range == inner_span.content_range
    updated_document = parse_prompt_document(result.text)
    assert [span.weight for span in updated_document.emphasis_spans] == [
        Decimal("1.10"),
        Decimal("1.25"),
    ]


def test_decrease_emphasis_updates_only_inner_nested_span() -> None:
    """Nested emphasis decreases should not disturb the enclosing shell."""

    document = parse_prompt_document("((cat:1.20) dog:1.10)")
    inner_span = document.emphasis_spans[1]

    result = decrease_emphasis(document, inner_span.content_range)

    assert result.text == "((cat:1.15) dog:1.10)"
    assert result.selection_range == inner_span.content_range
    updated_document = parse_prompt_document(result.text)
    assert [span.weight for span in updated_document.emphasis_spans] == [
        Decimal("1.10"),
        Decimal("1.15"),
    ]


def test_decrease_emphasis_neutral_unwrap_preserves_expected_plain_text_range() -> None:
    """Neutral unwrap should restore the inner plain text at the outer shell range."""

    document = parse_prompt_document("before, (cat:1.05), after")
    span = document.emphasis_spans[0]

    result = decrease_emphasis(document, span.content_range)

    assert result.text == "before, cat, after"
    assert result.selection_range is not None
    assert result.selection_range.slice(result.text) == "cat"
    assert (result.selection_range.start, result.selection_range.end) == (8, 11)


def test_set_emphasis_weight_updates_existing_shell_to_exact_value() -> None:
    """Exact emphasis setting should replace only the existing numeric weight."""

    document = parse_prompt_document("(cat:1.05)")

    result = set_emphasis_weight(
        document,
        document.emphasis_spans[0].content_range,
        weight=Decimal("1.20"),
    )

    assert result.text == "(cat:1.20)"
    assert result.selection_range == document.emphasis_spans[0].content_range


def test_set_emphasis_weight_unwraps_existing_shell_at_neutral() -> None:
    """Exact neutral emphasis should unwrap the existing shell immediately."""

    document = parse_prompt_document("(cat:1.20)")

    result = set_emphasis_weight(
        document,
        document.emphasis_spans[0].content_range,
        weight=Decimal("1.00"),
    )

    assert result.text == "cat"
    assert result.selection_range is not None
    assert result.selection_range.slice(result.text) == "cat"


def test_set_emphasis_weight_wraps_plain_selection_at_exact_weight() -> None:
    """Exact-weight setting should wrap plain selected text when no shell exists."""

    document = parse_prompt_document("cat")

    result = set_emphasis_weight(
        document,
        SourceRange(0, 3),
        weight=Decimal("0.95"),
    )

    assert result.text == "(cat:0.95)"
    assert result.selection_range is not None
    assert (result.selection_range.start, result.selection_range.end) == (1, 4)


def test_set_emphasis_weight_preserves_negative_exact_value() -> None:
    """Exact-weight setting should preserve signed emphasis values."""

    document = parse_prompt_document("(cat:1.20)")

    result = set_emphasis_weight(
        document,
        document.emphasis_spans[0].content_range,
        weight=Decimal("-1.234"),
    )

    assert result.text == "(cat:-1.23)"
    assert result.document.emphasis_spans[0].weight == Decimal("-1.23")
    assert result.selection_range == document.emphasis_spans[0].content_range


def test_replace_span_content_updates_inner_text_only() -> None:
    """Replacing emphasis content should preserve the existing shell and weight."""

    document = parse_prompt_document("(cat:1.20)")

    result = replace_span_content(document, document.emphasis_spans[0], "dog")

    assert result.text == "(dog:1.20)"
    assert result.selection_range is not None
    assert (result.selection_range.start, result.selection_range.end) == (1, 4)

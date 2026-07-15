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

"""Parse prompt text into a tolerant domain document model."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re

from .models import (
    EmphasisSpan,
    LoraSpan,
    PromptDocument,
    PromptSegment,
    SourceRange,
    SyntaxSpan,
    WildcardSpan,
)
from .syntax import (
    BRACKET_PAIRS,
    QUOTE_CHARACTERS,
    SyntaxKind,
    TOP_LEVEL_SEPARATOR_WHITESPACE,
    WildcardForm,
)
from .wildcard_syntax import PromptWildcardDelimiter, PromptWildcardSyntaxProfile
from .structural_scanner import is_structural_quote

_VALID_WEIGHT_RE = re.compile(r"(?:\d+(?:\.\d*)?|\.\d+)")
_VALID_LORA_WEIGHT_RE = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)")
_LORA_PREFIX = "lora:"


@dataclass(frozen=True, slots=True)
class _BracketFrame:
    """Track one open bracket while scanning prompt text."""

    opener: str
    expected_closer: str
    start_index: int
    literal: bool = False


@dataclass(frozen=True, slots=True)
class _RawEmphasisSpan:
    """Track one parsed emphasis span before nesting depth is assigned."""

    outer_range: SourceRange
    content_range: SourceRange
    weight_range: SourceRange
    weight: Decimal


def parse_prompt_document(
    text: str,
    wildcard_syntax_profile: PromptWildcardSyntaxProfile | None = None,
) -> PromptDocument:
    """Parse prompt text into a tolerant prompt-domain document."""

    wildcard_profile = wildcard_syntax_profile or PromptWildcardSyntaxProfile.default()
    alternate_wildcards = _find_alternate_wildcard_spans(text, wildcard_profile)
    alternate_wildcards_by_start = {
        span.outer_range.start: span for span in alternate_wildcards
    }
    segments: list[PromptSegment] = []
    emphasis_candidates: list[_RawEmphasisSpan] = []
    wildcard_spans: list[WildcardSpan] = list(alternate_wildcards)
    lora_spans: list[LoraSpan] = []
    bracket_stack: list[_BracketFrame] = []
    in_quote: str | None = None
    escape = False
    segment_start = 0
    index = 0

    while index < len(text):
        alternate_wildcard = alternate_wildcards_by_start.get(index)
        if alternate_wildcard is not None and not bracket_stack and in_quote is None:
            index = alternate_wildcard.outer_range.end
            continue

        character = text[index]
        if in_quote is not None:
            if escape:
                escape = False
            elif character == "\\":
                escape = True
            elif _is_quote_closer(text=text, index=index, quote=in_quote):
                in_quote = None
            index += 1
            continue

        if bracket_stack and bracket_stack[-1].literal:
            if character == "\\" and index + 1 < len(text):
                next_character = text[index + 1]
                if next_character == "(":
                    bracket_stack.append(
                        _BracketFrame(
                            opener="\\(",
                            expected_closer=")",
                            start_index=index,
                            literal=True,
                        )
                    )
                    index += 2
                    continue
                if next_character == ")" and bracket_stack[-1].opener == "\\(":
                    bracket_stack.pop()
                    index += 2
                    continue
            index += 1
            continue

        if _is_prompt_quote_opener(
            text=text,
            index=index,
            bracket_stack=bracket_stack,
        ):
            in_quote = character
            index += 1
            continue

        if character == "\\":
            if index + 1 >= len(text):
                index += 1
                continue
            next_character = text[index + 1]
            if next_character == "(":
                bracket_stack.append(
                    _BracketFrame(
                        opener="\\(",
                        expected_closer=")",
                        start_index=index,
                        literal=True,
                    )
                )
                index += 2
                continue
            index += 2
            continue

        if character in BRACKET_PAIRS:
            bracket_stack.append(
                _BracketFrame(
                    opener=character,
                    expected_closer=BRACKET_PAIRS[character],
                    start_index=index,
                )
            )
            index += 1
            continue

        if character in BRACKET_PAIRS.values() and bracket_stack:
            frame = bracket_stack[-1]
            if frame.expected_closer == character:
                bracket_stack.pop()
                if frame.opener == "(":
                    maybe_emphasis = _parse_emphasis_group(
                        text=text,
                        open_index=frame.start_index,
                        close_index=index,
                    )
                    if maybe_emphasis is not None:
                        emphasis_candidates.append(maybe_emphasis)
                elif frame.opener == "{" and _profile_supports_curly(wildcard_profile):
                    if not any(
                        open_frame.opener == "{" for open_frame in bracket_stack
                    ):
                        maybe_wildcard = _parse_wildcard_group(
                            text=text,
                            open_index=frame.start_index,
                            close_index=index,
                        )
                        if maybe_wildcard is not None:
                            wildcard_spans.append(maybe_wildcard)
                elif frame.opener == "<":
                    maybe_lora = _parse_lora_group(
                        text=text,
                        open_index=frame.start_index,
                        close_index=index,
                    )
                    if maybe_lora is not None:
                        lora_spans.append(maybe_lora)
            index += 1
            continue

        if character == "," and not bracket_stack:
            separator_end = index + 1
            while (
                separator_end < len(text)
                and text[separator_end] in TOP_LEVEL_SEPARATOR_WHITESPACE
            ):
                separator_end += 1
            segments.append(
                PromptSegment(
                    index=len(segments),
                    text=text[segment_start:index],
                    content_range=SourceRange(segment_start, index),
                    separator_range=SourceRange(index, separator_end),
                )
            )
            segment_start = separator_end
            index = separator_end
            continue

        index += 1

    has_trailing_comma = bool(text.rstrip().endswith(","))
    if segment_start < len(text):
        segments.append(
            PromptSegment(
                index=len(segments),
                text=text[segment_start:],
                content_range=SourceRange(segment_start, len(text)),
                separator_range=None,
            )
        )

    emphasis_spans = _assign_emphasis_depths(emphasis_candidates)
    ordered_wildcard_spans = _order_wildcard_spans(wildcard_spans)
    ordered_lora_spans = _assign_lora_depths(lora_spans)
    syntax_spans = _build_syntax_spans(
        emphasis_spans=emphasis_spans,
        wildcard_spans=ordered_wildcard_spans,
        lora_spans=ordered_lora_spans,
    )
    return PromptDocument(
        source_text=text,
        segments=tuple(segments),
        syntax_spans=syntax_spans,
        emphasis_spans=emphasis_spans,
        wildcard_spans=ordered_wildcard_spans,
        lora_spans=ordered_lora_spans,
        has_trailing_comma=has_trailing_comma,
    )


def _parse_emphasis_group(
    *,
    text: str,
    open_index: int,
    close_index: int,
) -> _RawEmphasisSpan | None:
    """Return one emphasis span when a parenthesized group is weighted."""

    colon_index = _find_final_top_level_colon(
        text=text,
        start=open_index + 1,
        end=close_index,
    )
    if colon_index is None:
        return None
    weight_start = colon_index + 1
    weight_text = text[weight_start:close_index]
    if not weight_text or weight_text.strip() != weight_text:
        return None
    if _VALID_WEIGHT_RE.fullmatch(weight_text) is None:
        return None
    try:
        weight = Decimal(weight_text)
    except InvalidOperation:
        return None
    return _RawEmphasisSpan(
        outer_range=SourceRange(open_index, close_index + 1),
        content_range=SourceRange(open_index + 1, colon_index),
        weight_range=SourceRange(weight_start, close_index),
        weight=weight,
    )


def _quote_delimiters_active(bracket_stack: list[_BracketFrame]) -> bool:
    """Return whether quote characters should affect scanner structure."""

    return not any(frame.opener == "<" for frame in bracket_stack)


def _is_prompt_quote_opener(
    *,
    text: str,
    index: int,
    bracket_stack: list[_BracketFrame],
) -> bool:
    """Return whether one character opens a quote in the prompt scan."""

    character = text[index]
    return (
        character in QUOTE_CHARACTERS
        and _quote_delimiters_active(bracket_stack)
        and _is_quote_delimiter(text=text, index=index, quote=character)
    )


def _is_nested_quote_opener(
    *,
    text: str,
    index: int,
    bracket_stack: list[tuple[str, bool]],
) -> bool:
    """Return whether one character opens a quote in a nested syntax scan."""

    character = text[index]
    return (
        character in QUOTE_CHARACTERS
        and not any(
            expected_closer == ">" for expected_closer, _literal in bracket_stack
        )
        and _is_quote_delimiter(text=text, index=index, quote=character)
    )


def _is_quote_closer(*, text: str, index: int, quote: str) -> bool:
    """Return whether one character closes the current quote."""

    return text[index] == quote and _is_quote_delimiter(
        text=text,
        index=index,
        quote=quote,
    )


def _is_quote_delimiter(*, text: str, index: int, quote: str) -> bool:
    """Return whether a quote mark is structural rather than an apostrophe."""

    return is_structural_quote(text, index, quote)


def _find_final_top_level_colon(
    *,
    text: str,
    start: int,
    end: int,
) -> int | None:
    """Return the last top-level colon inside one parenthesized group."""

    colon_index: int | None = None
    bracket_stack: list[tuple[str, bool]] = []
    in_quote: str | None = None
    escape = False
    index = start

    while index < end:
        character = text[index]
        if in_quote is not None:
            if escape:
                escape = False
            elif character == "\\":
                escape = True
            elif _is_quote_closer(text=text, index=index, quote=in_quote):
                in_quote = None
            index += 1
            continue

        if bracket_stack and bracket_stack[-1][1]:
            if character == "\\" and index + 1 < end:
                next_character = text[index + 1]
                if next_character == "(":
                    bracket_stack.append((")", True))
                    index += 2
                    continue
                if next_character == ")" and bracket_stack[-1][0] == ")":
                    bracket_stack.pop()
                    index += 2
                    continue
            index += 1
            continue

        if _is_nested_quote_opener(
            text=text,
            index=index,
            bracket_stack=bracket_stack,
        ):
            in_quote = character
            index += 1
            continue

        if character == "\\":
            if index + 1 >= end:
                index += 1
                continue
            next_character = text[index + 1]
            if next_character == "(":
                bracket_stack.append((")", True))
                index += 2
                continue
            index += 2
            continue

        if character in BRACKET_PAIRS:
            bracket_stack.append((BRACKET_PAIRS[character], False))
            index += 1
            continue

        if character in BRACKET_PAIRS.values() and bracket_stack:
            if bracket_stack[-1][0] == character:
                bracket_stack.pop()
            index += 1
            continue

        if character == ":" and not bracket_stack:
            colon_index = index
        index += 1

    return colon_index


def _parse_wildcard_group(
    *,
    text: str,
    open_index: int,
    close_index: int,
) -> WildcardSpan | None:
    """Return one wildcard span when balanced brace content matches a supported form."""

    raw_content = text[open_index + 1 : close_index]
    if not raw_content:
        return None
    if raw_content.strip() != raw_content:
        return None
    if "{" in raw_content or "}" in raw_content:
        return None

    wildcard_form, identifier, csv_column, tag = _parse_wildcard_content(raw_content)
    if wildcard_form is None or identifier is None:
        return None

    return WildcardSpan(
        outer_range=SourceRange(open_index, close_index + 1),
        content_range=SourceRange(open_index + 1, close_index),
        wildcard_form=wildcard_form,
        identifier=identifier,
        csv_column=csv_column,
        tag=tag,
    )


def _parse_lora_group(
    *,
    text: str,
    open_index: int,
    close_index: int,
) -> LoraSpan | None:
    """Return one LoRA span when angle-bracket content matches Prompt Control."""

    raw_content = text[open_index + 1 : close_index]
    if not raw_content.startswith(_LORA_PREFIX):
        return None
    remainder_start = open_index + 1 + len(_LORA_PREFIX)
    if remainder_start >= close_index:
        return None
    name_end = text.find(":", remainder_start, close_index)
    if name_end < 0 or name_end == remainder_start:
        return None
    name_text = text[remainder_start:name_end]
    if "<" in name_text or ">" in name_text or ":" in name_text:
        return None

    first_field_start = name_end + 1
    first_field_end = _next_colon_or_end(text, first_field_start, close_index)
    first_weight = _parse_lora_weight_field(
        text=text,
        field_start=first_field_start,
        field_end=first_field_end,
    )
    if first_weight is None:
        return None

    second_weight: tuple[SourceRange, Decimal] | None = None
    block_weights_range: SourceRange | None = None
    if first_field_end < close_index:
        second_field_start = first_field_end + 1
        second_field_end = _next_colon_or_end(text, second_field_start, close_index)
        maybe_second_weight = _parse_lora_weight_field(
            text=text,
            field_start=second_field_start,
            field_end=second_field_end,
        )
        if maybe_second_weight is None:
            block_weights_range = SourceRange(second_field_start, close_index)
        else:
            second_weight = maybe_second_weight
            if second_field_end < close_index:
                block_weights_range = SourceRange(second_field_end + 1, close_index)

    return LoraSpan(
        outer_range=SourceRange(open_index, close_index + 1),
        name_range=SourceRange(remainder_start, name_end),
        first_weight_range=first_weight[0],
        first_weight=first_weight[1],
        second_weight_range=None if second_weight is None else second_weight[0],
        second_weight=None if second_weight is None else second_weight[1],
        block_weights_range=block_weights_range,
    )


def _next_colon_or_end(text: str, start: int, end: int) -> int:
    """Return the next colon position or the supplied end boundary."""

    colon_index = text.find(":", start, end)
    return end if colon_index < 0 else colon_index


def _parse_lora_weight_field(
    *,
    text: str,
    field_start: int,
    field_end: int,
) -> tuple[SourceRange, Decimal] | None:
    """Parse one Prompt Control LoRA weight field and return its numeric range."""

    raw_field = text[field_start:field_end]
    if not raw_field:
        return None
    leading_whitespace = len(raw_field) - len(raw_field.lstrip(" \t"))
    weight_text = raw_field[leading_whitespace:]
    if not weight_text or weight_text.strip() != weight_text:
        return None
    if _VALID_LORA_WEIGHT_RE.fullmatch(weight_text) is None:
        return None
    try:
        weight = Decimal(weight_text)
    except InvalidOperation:
        return None
    weight_start = field_start + leading_whitespace
    return SourceRange(weight_start, field_end), weight


def _parse_wildcard_content(
    raw_content: str,
) -> tuple[WildcardForm | None, str | None, str | None, str | None]:
    """Parse wildcard placeholder content into one normalized wildcard description."""

    base_content, tag = _split_wildcard_tag(raw_content)
    if base_content.startswith("csv:"):
        remainder = base_content[4:]
        if remainder.count(":") != 1:
            return None, None, None, None
        identifier_text, separator, csv_column = remainder.partition(":")
        if not separator:
            return None, None, None, None
        identifier = _normalize_wildcard_identifier(identifier_text)
        normalized_column = _normalize_csv_column_name(csv_column)
        if identifier is None or normalized_column is None:
            return None, None, None, None
        return WildcardForm.CSV, identifier, normalized_column, tag

    if ":" in base_content:
        return None, None, None, None

    identifier = _normalize_wildcard_identifier(base_content)
    if identifier is None:
        return None, None, None, None
    return WildcardForm.SIMPLE, identifier, None, tag


def _split_wildcard_tag(raw_content: str) -> tuple[str, str | None]:
    """Split one optional wildcard tag suffix from placeholder content."""

    base_content, separator, tag = raw_content.partition("|")
    if not separator:
        return raw_content, None
    if not tag or tag.strip() != tag:
        return raw_content, None
    return base_content, tag


def _normalize_wildcard_identifier(raw_identifier: str) -> str | None:
    """Normalize one wildcard identifier path or return None when invalid."""

    if not raw_identifier or raw_identifier.strip() != raw_identifier:
        return None
    if "\\" in raw_identifier or ":" in raw_identifier:
        return None

    parts = raw_identifier.split("/")
    normalized_parts: list[str] = []
    for part in parts:
        if not part or part.strip() != part or part in {".", ".."}:
            return None
        normalized_parts.append(part)
    return "/".join(normalized_parts)


def _normalize_csv_column_name(raw_column: str) -> str | None:
    """Normalize one CSV wildcard column name or return None when invalid."""

    if not raw_column or raw_column.strip() != raw_column:
        return None
    return raw_column


def _find_alternate_wildcard_spans(
    text: str,
    wildcard_profile: PromptWildcardSyntaxProfile,
) -> tuple[WildcardSpan, ...]:
    """Return non-curly wildcard spans for the configured syntax profile."""

    spans: list[WildcardSpan] = []
    for delimiter in wildcard_profile.delimiters():
        if delimiter == PromptWildcardDelimiter("{", "}"):
            continue
        spans.extend(_find_delimited_wildcard_spans(text, delimiter))
    return tuple(
        sorted(
            spans,
            key=lambda span: (span.outer_range.start, span.outer_range.end),
        )
    )


def _find_delimited_wildcard_spans(
    text: str,
    delimiter: PromptWildcardDelimiter,
) -> tuple[WildcardSpan, ...]:
    """Return wildcard spans enclosed by one non-curly delimiter pair."""

    spans: list[WildcardSpan] = []
    prefix = delimiter.prefix
    suffix = delimiter.suffix
    index = 0
    while index < len(text):
        open_index = text.find(prefix, index)
        if open_index < 0:
            break
        content_start = open_index + len(prefix)
        close_index = text.find(suffix, content_start)
        if close_index < 0:
            break
        raw_content = text[content_start:close_index]
        wildcard_form, identifier, csv_column, tag = _parse_wildcard_content(
            raw_content
        )
        outer_end = close_index + len(suffix)
        if wildcard_form is not None and identifier is not None:
            spans.append(
                WildcardSpan(
                    outer_range=SourceRange(open_index, outer_end),
                    content_range=SourceRange(content_start, close_index),
                    wildcard_form=wildcard_form,
                    identifier=identifier,
                    csv_column=csv_column,
                    tag=tag,
                )
            )
        index = outer_end
    return tuple(spans)


def _profile_supports_curly(profile: PromptWildcardSyntaxProfile) -> bool:
    """Return whether the wildcard profile should parse curly-brace placeholders."""

    return any(
        delimiter == PromptWildcardDelimiter("{", "}")
        for delimiter in profile.delimiters()
    )


def _assign_emphasis_depths(
    emphasis_candidates: list[_RawEmphasisSpan],
) -> tuple[EmphasisSpan, ...]:
    """Return emphasis spans ordered by source range with nesting depth assigned."""

    active_end_positions: list[int] = []
    ordered_candidates = sorted(
        emphasis_candidates,
        key=lambda span: (span.outer_range.start, span.outer_range.end),
    )
    finalized_spans: list[EmphasisSpan] = []
    for candidate in ordered_candidates:
        active_end_positions = [
            end_position
            for end_position in active_end_positions
            if end_position > candidate.outer_range.start
        ]
        finalized_spans.append(
            EmphasisSpan(
                outer_range=candidate.outer_range,
                content_range=candidate.content_range,
                weight_range=candidate.weight_range,
                weight=candidate.weight,
                depth=len(active_end_positions),
            )
        )
        active_end_positions.append(candidate.outer_range.end)
    return tuple(finalized_spans)


def _order_wildcard_spans(
    wildcard_spans: list[WildcardSpan],
) -> tuple[WildcardSpan, ...]:
    """Return wildcard spans ordered deterministically by their source range."""

    return tuple(
        sorted(
            wildcard_spans,
            key=lambda span: (span.outer_range.start, span.outer_range.end),
        )
    )


def _assign_lora_depths(
    lora_spans: list[LoraSpan],
) -> tuple[LoraSpan, ...]:
    """Return LoRA spans ordered by source range with nesting depth assigned."""

    active_end_positions: list[int] = []
    ordered_spans = sorted(
        lora_spans,
        key=lambda span: (span.outer_range.start, span.outer_range.end),
    )
    finalized_spans: list[LoraSpan] = []
    for span in ordered_spans:
        active_end_positions = [
            end_position
            for end_position in active_end_positions
            if end_position > span.outer_range.start
        ]
        finalized_spans.append(
            LoraSpan(
                outer_range=span.outer_range,
                name_range=span.name_range,
                first_weight_range=span.first_weight_range,
                first_weight=span.first_weight,
                second_weight_range=span.second_weight_range,
                second_weight=span.second_weight,
                block_weights_range=span.block_weights_range,
                depth=len(active_end_positions),
            )
        )
        active_end_positions.append(span.outer_range.end)
    return tuple(finalized_spans)


def _build_syntax_spans(
    *,
    emphasis_spans: tuple[EmphasisSpan, ...],
    wildcard_spans: tuple[WildcardSpan, ...],
    lora_spans: tuple[LoraSpan, ...],
) -> tuple[SyntaxSpan, ...]:
    """Return one deterministic syntax span list built from all parsed syntax spans."""

    syntax_spans = [
        SyntaxSpan(
            kind=SyntaxKind.EMPHASIS,
            source_range=span.outer_range,
            depth=span.depth,
        )
        for span in emphasis_spans
    ]
    syntax_spans.extend(
        SyntaxSpan(
            kind=SyntaxKind.WILDCARD,
            source_range=span.outer_range,
            depth=span.depth,
        )
        for span in wildcard_spans
    )
    syntax_spans.extend(
        SyntaxSpan(
            kind=SyntaxKind.LORA,
            source_range=span.outer_range,
            depth=span.depth,
        )
        for span in lora_spans
    )
    return tuple(
        sorted(
            syntax_spans,
            key=lambda span: (span.source_range.start, span.source_range.end),
        )
    )


__all__ = ["parse_prompt_document"]

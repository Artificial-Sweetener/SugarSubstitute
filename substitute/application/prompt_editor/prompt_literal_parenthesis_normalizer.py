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

"""Canonicalize prompt parentheses from explicit semantic knowledge."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import Enum

from substitute.domain.prompt import parse_prompt_document
from substitute.domain.prompt.emphasis_semantics import (
    format_generated_emphasis_weight,
    implicit_emphasis_weight,
)
from substitute.domain.prompt.structural_scanner import (
    PromptParenthesisPair,
    balanced_parenthesis_pairs,
)

PromptTagMembership = Callable[[str], bool]


class PromptParenthesisTransitionKind(str, Enum):
    """Identify a semantic source rewrite produced by canonicalization."""

    IMPLICIT_EMPHASIS = "implicit_emphasis"
    KNOWN_LITERAL_TAG = "known_literal_tag"
    ESCAPED_LITERAL_TO_EMPHASIS = "escaped_literal_to_emphasis"


@dataclass(frozen=True, slots=True)
class PromptParenthesisTransition:
    """Describe one semantic parenthesis rewrite in original source coordinates."""

    kind: PromptParenthesisTransitionKind
    source_start: int
    source_end: int
    nesting_depth: int = 1


@dataclass(frozen=True, slots=True)
class PromptParenthesisCanonicalization:
    """Return canonical source, boundary mappings, and semantic transitions."""

    text: str
    boundary_positions: tuple[int, ...]
    transitions: tuple[PromptParenthesisTransition, ...] = ()


@dataclass(frozen=True, slots=True)
class PromptGeneratedEmphasis:
    """Identify one explicit emphasis group generated from implicit parentheses."""

    source_start: int
    source_end: int
    nesting_depth: int


def canonicalize_prompt_parentheses(
    text: str,
    *,
    is_known_tag: PromptTagMembership | None = None,
    force_literal: bool = False,
    generated_emphases: tuple[PromptGeneratedEmphasis, ...] = (),
) -> PromptParenthesisCanonicalization:
    """Canonicalize balanced parentheses using tag knowledge and explicit weights."""

    known_tag = is_known_tag or _never_known_tag
    document = parse_prompt_document(text)
    replacements: list[tuple[int, int, str, PromptParenthesisTransition]] = []
    for segment in document.segments:
        leading = len(segment.text) - len(segment.text.lstrip(" \t"))
        trailing = len(segment.text) - len(segment.text.rstrip(" \t"))
        content_start = segment.content_range.start + leading
        content_end = segment.content_range.end - trailing
        if content_start >= content_end:
            continue
        segment_content = text[content_start:content_end]
        pairs = balanced_parenthesis_pairs(segment_content)
        if not pairs:
            continue
        if force_literal or known_tag(segment_content):
            literal_text = _escape_balanced_parentheses(segment_content, pairs)
            if literal_text != segment_content:
                replacements.append(
                    (
                        content_start,
                        content_end,
                        literal_text,
                        PromptParenthesisTransition(
                            kind=PromptParenthesisTransitionKind.KNOWN_LITERAL_TAG,
                            source_start=content_start,
                            source_end=content_end,
                        ),
                    )
                )
            continue
        canonical_text, depth = _canonicalize_unknown_parentheses(
            segment_content,
            pairs,
            generated_emphases=tuple(
                PromptGeneratedEmphasis(
                    source_start=generated.source_start - content_start,
                    source_end=generated.source_end - content_start,
                    nesting_depth=generated.nesting_depth,
                )
                for generated in generated_emphases
                if content_start <= generated.source_start
                and generated.source_end <= content_end
            ),
        )
        if canonical_text != segment_content:
            replacements.append(
                (
                    content_start,
                    content_end,
                    canonical_text,
                    PromptParenthesisTransition(
                        kind=PromptParenthesisTransitionKind.IMPLICIT_EMPHASIS,
                        source_start=content_start,
                        source_end=content_end,
                        nesting_depth=depth,
                    ),
                )
            )
    return _apply_canonical_replacements(text, replacements)


def normalize_literal_parentheses_for_storage(text: str) -> str:
    """Return canonical parenthesis source without external tag knowledge."""

    return canonicalize_prompt_parentheses(text).text


def normalize_literal_parentheses_for_typed_edit(text: str) -> str:
    """Return canonical parenthesis source for one completed typed scope."""

    return canonicalize_prompt_parentheses(text).text


def is_explicit_weighted_emphasis_group(text: str) -> bool:
    """Return whether text is exactly one syntactically valid weighted shell."""

    document = parse_prompt_document(text)
    if len(document.segments) != 1 or document.has_trailing_comma:
        return False
    return any(
        span.outer_range.start == 0 and span.outer_range.end == len(text)
        for span in document.emphasis_spans
    )


def _canonicalize_unknown_parentheses(
    text: str,
    pairs: tuple[PromptParenthesisPair, ...],
    *,
    generated_emphases: tuple[PromptGeneratedEmphasis, ...] = (),
) -> tuple[str, int]:
    """Rewrite implicit groups while preserving already explicit emphasis."""

    by_open = {pair.opening_index: pair for pair in pairs}
    generated_depths = {
        (generated.source_start, generated.source_end): generated.nesting_depth
        for generated in generated_emphases
    }
    max_depth = 1

    def render(start: int, end: int) -> str:
        nonlocal max_depth
        parts: list[str] = []
        cursor = start
        while cursor < end:
            pair = by_open.get(cursor)
            if pair is None or pair.closing_index >= end:
                parts.append(text[cursor])
                cursor += 1
                continue
            group_text = text[pair.opening_index : pair.closing_index + 1]
            if is_explicit_weighted_emphasis_group(group_text):
                emphasis_span = parse_prompt_document(group_text).emphasis_spans[0]
                content_start = pair.opening_index + emphasis_span.content_range.start
                content_end = pair.opening_index + emphasis_span.content_range.end
                weight_text = emphasis_span.weight_range.slice(group_text)
                parts.append(f"({render(content_start, content_end)}:{weight_text})")
                cursor = pair.closing_index + 1
                continue
            depth, inner_start, inner_end = _collapsible_implicit_nesting(
                text,
                pair,
                by_open,
                generated_depths,
            )
            max_depth = max(max_depth, depth)
            inner = render(inner_start, inner_end)
            weight = format_generated_emphasis_weight(implicit_emphasis_weight(depth))
            parts.append(f"({inner}:{weight})")
            cursor = pair.closing_index + 1
        return "".join(parts)

    return render(0, len(text)), max_depth


def _collapsible_implicit_nesting(
    text: str,
    pair: PromptParenthesisPair,
    by_open: dict[int, PromptParenthesisPair],
    generated_depths: dict[tuple[int, int], int],
) -> tuple[int, int, int]:
    """Collapse directly nested implicit and previously generated emphasis shells."""

    depth = 1
    inner_start = pair.opening_index + 1
    inner_end = pair.closing_index
    while inner_start < inner_end:
        nested = by_open.get(inner_start)
        if nested is None or nested.closing_index != inner_end - 1:
            break
        nested_text = text[nested.opening_index : nested.closing_index + 1]
        if is_explicit_weighted_emphasis_group(nested_text):
            generated_depth = generated_depths.get(
                (nested.opening_index, nested.closing_index + 1)
            )
            if generated_depth is None:
                break
            emphasis_span = parse_prompt_document(nested_text).emphasis_spans[0]
            depth += generated_depth
            inner_start = nested.opening_index + emphasis_span.content_range.start
            inner_end = nested.opening_index + emphasis_span.content_range.end
            continue
        depth += 1
        inner_start = nested.opening_index + 1
        inner_end = nested.closing_index
    return depth, inner_start, inner_end


def _escape_balanced_parentheses(
    text: str,
    pairs: tuple[PromptParenthesisPair, ...],
) -> str:
    """Escape every parenthesis participating in a balanced literal tag."""

    indices = {
        index for pair in pairs for index in (pair.opening_index, pair.closing_index)
    }
    return "".join(
        f"\\{character}" if index in indices else character
        for index, character in enumerate(text)
    )


def _apply_canonical_replacements(
    text: str,
    replacements: list[tuple[int, int, str, PromptParenthesisTransition]],
) -> PromptParenthesisCanonicalization:
    """Apply non-overlapping rewrites and map every original source boundary."""

    if not replacements:
        return PromptParenthesisCanonicalization(
            text=text,
            boundary_positions=tuple(range(len(text) + 1)),
        )
    parts: list[str] = []
    boundary_positions: list[int | None] = [None] * (len(text) + 1)
    source_cursor = 0
    target_cursor = 0
    for start, end, replacement, _transition in replacements:
        unchanged = text[source_cursor:start]
        parts.append(unchanged)
        for source_index in range(source_cursor, start + 1):
            boundary_positions[source_index] = (
                target_cursor + source_index - source_cursor
            )
        target_cursor += len(unchanged)
        parts.append(replacement)
        local_mapping = _sequence_boundary_mapping(text[start:end], replacement)
        for offset, mapped in enumerate(local_mapping):
            boundary_positions[start + offset] = target_cursor + mapped
        target_cursor += len(replacement)
        source_cursor = end
    suffix = text[source_cursor:]
    parts.append(suffix)
    for source_index in range(source_cursor, len(text) + 1):
        boundary_positions[source_index] = target_cursor + source_index - source_cursor
    return PromptParenthesisCanonicalization(
        text="".join(parts),
        boundary_positions=_complete_boundary_positions(boundary_positions),
        transitions=tuple(replacement[3] for replacement in replacements),
    )


def _sequence_boundary_mapping(source: str, target: str) -> tuple[int, ...]:
    """Map source boundaries through one deterministic local source rewrite."""

    positions: list[int | None] = [None] * (len(source) + 1)
    for tag, source_start, source_end, target_start, target_end in SequenceMatcher(
        None, source, target, autojunk=False
    ).get_opcodes():
        positions[source_start] = target_start
        positions[source_end] = target_end
        if tag == "equal":
            for offset in range(source_end - source_start + 1):
                positions[source_start + offset] = target_start + offset
        else:
            source_length = source_end - source_start
            target_length = target_end - target_start
            for offset in range(1, source_length):
                positions[source_start + offset] = target_start + min(
                    offset, target_length
                )
    last = 0
    for index, position in enumerate(positions):
        if position is None:
            positions[index] = last
        else:
            last = position
    return _complete_boundary_positions(positions)


def _complete_boundary_positions(
    positions: list[int | None],
) -> tuple[int, ...]:
    """Return complete positions or reject an internal mapping defect."""

    completed: list[int] = []
    for position in positions:
        if position is None:
            raise ValueError("Canonical prompt boundary mapping is incomplete.")
        completed.append(position)
    return tuple(completed)


def _never_known_tag(_text: str) -> bool:
    """Return false for canonicalizers without a prepared tag snapshot."""

    return False


__all__ = [
    "PromptGeneratedEmphasis",
    "PromptParenthesisCanonicalization",
    "PromptParenthesisTransition",
    "PromptParenthesisTransitionKind",
    "PromptTagMembership",
    "canonicalize_prompt_parentheses",
    "is_explicit_weighted_emphasis_group",
    "normalize_literal_parentheses_for_storage",
    "normalize_literal_parentheses_for_typed_edit",
]

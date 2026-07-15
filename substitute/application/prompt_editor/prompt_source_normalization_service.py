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

"""Normalize prompt source text at editor ingestion boundaries."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from substitute.application.ports import PromptTagLexiconSnapshot
from substitute.domain.prompt import normalize_prompt_weights, parse_prompt_document
from substitute.domain.prompt.structural_scanner import balanced_parenthesis_pairs

from .prompt_literal_parenthesis_normalizer import (
    PromptGeneratedEmphasis,
    PromptParenthesisCanonicalization,
    PromptParenthesisTransition,
    PromptParenthesisTransitionKind,
    canonicalize_prompt_parentheses,
    is_explicit_weighted_emphasis_group,
)


@dataclass(frozen=True, slots=True)
class PromptSourceNormalization:
    """Describe normalized prompt source text and original boundary remapping."""

    text: str
    boundary_positions: tuple[int, ...]
    transitions: tuple[PromptParenthesisTransition, ...] = ()


class PromptSourceNormalizationService:
    """Normalize prompt source text before it enters the editor surface."""

    def __init__(
        self,
        *,
        tag_snapshot: PromptTagLexiconSnapshot | None = None,
    ) -> None:
        """Bind normalization to one immutable, I/O-free exact-tag snapshot."""

        self._tag_snapshot = tag_snapshot or PromptTagLexiconSnapshot()

    def normalize_for_storage(self, text: str) -> PromptSourceNormalization:
        """Normalize prompt source into the canonical stored editor form."""

        return _normalize_canonical_source_with_boundaries(
            text,
            tag_snapshot=self._tag_snapshot,
        )

    def normalize_for_paste(self, text: str) -> PromptSourceNormalization:
        """Normalize pasted prompt source text into the canonical stored form."""

        return self.normalize_for_storage(text)

    def normalize_for_paste_range(
        self,
        text: str,
        *,
        start: int,
        end: int,
    ) -> PromptSourceNormalization:
        """Normalize only the pasted source range inside the full prompt text."""

        return _normalize_source_range_with_boundaries(
            text,
            start=start,
            end=end,
            normalizer=lambda value: _normalize_canonical_source_with_boundaries(
                value,
                tag_snapshot=self._tag_snapshot,
            ),
        )

    def normalize_for_typed_edit(self, text: str) -> PromptSourceNormalization:
        """Normalize live typed literal parentheses without rewriting weights."""

        if "(" not in text and ")" not in text:
            return PromptSourceNormalization(
                text=text,
                boundary_positions=tuple(range(len(text) + 1)),
            )
        return _parenthesis_normalization(
            canonicalize_prompt_parentheses(
                text,
                is_known_tag=self._tag_snapshot.contains_prompt_tag,
            )
        )

    def normalize_for_typed_edit_range(
        self,
        text: str,
        *,
        start: int,
        end: int,
        replacement_text: str,
        generated_emphases: tuple[PromptGeneratedEmphasis, ...] = (),
    ) -> PromptSourceNormalization:
        """Normalize only parenthesis syntax introduced by one typed edit."""

        reclassification = _normalize_typed_emphasis_reclassification(
            text,
            start=start,
            end=end,
            replacement_text=replacement_text,
        )
        if reclassification is not None:
            return reclassification

        scope = _typed_parenthesis_scope(
            text,
            start=start,
            end=end,
            replacement_text=replacement_text,
        )
        if scope is None:
            return PromptSourceNormalization(
                text=text,
                boundary_positions=tuple(range(len(text) + 1)),
            )
        scoped_generated_emphases = tuple(
            PromptGeneratedEmphasis(
                source_start=generated.source_start - scope[0],
                source_end=generated.source_end - scope[0],
                nesting_depth=generated.nesting_depth,
            )
            for generated in generated_emphases
            if scope[0] <= generated.source_start and generated.source_end <= scope[1]
        )
        return _normalize_source_range_with_boundaries(
            text,
            start=scope[0],
            end=scope[1],
            normalizer=lambda value: _parenthesis_normalization(
                canonicalize_prompt_parentheses(
                    value,
                    is_known_tag=self._tag_snapshot.contains_prompt_tag,
                    generated_emphases=scoped_generated_emphases,
                )
            ),
        )

    def normalize_literal_parentheses_for_storage(self, text: str) -> str:
        """Return text with literal parenthesized groups escaped for storage."""

        return canonicalize_prompt_parentheses(
            text,
            is_known_tag=self._tag_snapshot.contains_prompt_tag,
        ).text


def _parenthesis_normalization(
    result: PromptParenthesisCanonicalization,
) -> PromptSourceNormalization:
    """Adapt the authoritative parenthesis result to source normalization."""

    return PromptSourceNormalization(
        text=result.text,
        boundary_positions=result.boundary_positions,
        transitions=result.transitions,
    )


def _normalize_typed_emphasis_reclassification(
    text: str,
    *,
    start: int,
    end: int,
    replacement_text: str,
) -> PromptSourceNormalization | None:
    """Return a local unescape when one typed edit creates weighted emphasis."""

    scope = _typed_emphasis_reclassification_scope(
        text,
        start=start,
        end=end,
        replacement_text=replacement_text,
    )
    if scope is None:
        return None
    source_slice = text[scope[0] : scope[1]]
    candidate = _unescaped_parenthesis_candidate(source_slice)
    if candidate is None or not is_explicit_weighted_emphasis_group(candidate):
        return None

    normalized_text = f"{text[: scope[0]]}{candidate}{text[scope[1] :]}"
    removed_indices = (scope[0], scope[1] - 2)
    boundary_positions = tuple(
        index - sum(1 for removed_index in removed_indices if removed_index < index)
        for index in range(len(text) + 1)
    )
    return PromptSourceNormalization(
        text=normalized_text,
        boundary_positions=boundary_positions,
        transitions=(
            PromptParenthesisTransition(
                kind=(PromptParenthesisTransitionKind.ESCAPED_LITERAL_TO_EMPHASIS),
                source_start=scope[0],
                source_end=scope[1],
            ),
        ),
    )


def _typed_emphasis_reclassification_scope(
    text: str,
    *,
    start: int,
    end: int,
    replacement_text: str,
) -> tuple[int, int] | None:
    """Return the escaped group range that one typed weight edit may reclassify."""

    if end != start + 1 or len(replacement_text) != 1:
        return None
    if replacement_text not in _TYPED_EMPHASIS_RECLASSIFICATION_CHARACTERS:
        return None
    return _enclosing_escaped_parenthesis_group(text, start)


def _enclosing_escaped_parenthesis_group(
    text: str,
    position: int,
) -> tuple[int, int] | None:
    """Return the smallest escaped literal parenthesis group containing position."""

    if not 0 <= position <= len(text):
        return None

    opening_stack: list[int] = []
    match: tuple[int, int] | None = None
    index = 0
    while index < len(text) - 1:
        if _escaped_parenthesis_pair_at(text, index, "("):
            opening_stack.append(index)
            index += 2
            continue
        if _escaped_parenthesis_pair_at(text, index, ")") and opening_stack:
            opening_index = opening_stack.pop()
            closing_end = index + 2
            if opening_index < position < closing_end:
                candidate = (opening_index, closing_end)
                if match is None or closing_end - opening_index < match[1] - match[0]:
                    match = candidate
            index += 2
            continue
        index += 1

    return match


def _escaped_parenthesis_pair_at(text: str, index: int, parenthesis: str) -> bool:
    """Return whether index starts one storage-escaped parenthesis pair."""

    return (
        index + 1 < len(text)
        and text[index] == "\\"
        and text[index + 1] == parenthesis
        and not _is_escaped_source_character(text, index)
    )


def _unescaped_parenthesis_candidate(text: str) -> str | None:
    """Return text with exactly the outer storage paren escapes removed."""

    if len(text) < 4 or not text.startswith(r"\(") or not text.endswith(r"\)"):
        return None
    return f"({text[2:-2]})"


def _normalize_canonical_source_with_boundaries(
    text: str,
    *,
    tag_snapshot: PromptTagLexiconSnapshot,
) -> PromptSourceNormalization:
    """Normalize literal parentheses and parsed weights with source boundary mapping."""

    literal_normalization = _parenthesis_normalization(
        canonicalize_prompt_parentheses(
            text,
            is_known_tag=tag_snapshot.contains_prompt_tag,
        )
    )
    weight_normalization = normalize_prompt_weights(literal_normalization.text)
    return PromptSourceNormalization(
        text=weight_normalization.text,
        boundary_positions=tuple(
            weight_normalization.boundary_positions[position]
            for position in literal_normalization.boundary_positions
        ),
        transitions=literal_normalization.transitions,
    )


def _normalize_source_range_with_boundaries(
    text: str,
    *,
    start: int,
    end: int,
    normalizer: Callable[[str], PromptSourceNormalization],
) -> PromptSourceNormalization:
    """Normalize a source slice while preserving surrounding text verbatim."""

    if start < 0 or end < start or end > len(text):
        raise ValueError("Prompt normalization range is outside the source text.")
    if start == end:
        return PromptSourceNormalization(
            text=text,
            boundary_positions=tuple(range(len(text) + 1)),
        )

    prefix = text[:start]
    source_slice = text[start:end]
    suffix = text[end:]
    normalized_slice = normalizer(source_slice)
    normalized_text = f"{prefix}{normalized_slice.text}{suffix}"
    delta = len(normalized_slice.text) - len(source_slice)

    boundary_positions: list[int] = []
    for index in range(len(text) + 1):
        if index < start:
            boundary_positions.append(index)
        elif index <= end:
            boundary_positions.append(
                start + normalized_slice.boundary_positions[index - start]
            )
        else:
            boundary_positions.append(index + delta)

    return PromptSourceNormalization(
        text=normalized_text,
        boundary_positions=tuple(boundary_positions),
        transitions=tuple(
            PromptParenthesisTransition(
                kind=transition.kind,
                source_start=start + transition.source_start,
                source_end=start + transition.source_end,
                nesting_depth=transition.nesting_depth,
            )
            for transition in normalized_slice.transitions
        ),
    )


def _typed_parenthesis_scope(
    text: str,
    *,
    start: int,
    end: int,
    replacement_text: str,
) -> tuple[int, int] | None:
    """Return the balanced parenthesis scope introduced by one typed edit."""

    if len(replacement_text) != 1 or end != start + 1:
        return None
    if replacement_text == ")":
        opening_index = _matching_opening_parenthesis(text, close_index=start)
        if opening_index is None:
            return None
        scope = _containing_segment_scope(text, opening_index, start + 1)
        if _closed_pair_has_unmatched_ancestor(
            text,
            scope=scope,
            opening_index=opening_index,
            closing_index=start,
        ):
            return None
        return scope
    if replacement_text == "(":
        closing_index = _matching_closing_parenthesis(text, open_index=start)
        if closing_index is None:
            return None
        return _containing_segment_scope(text, start, closing_index + 1)
    return None


def _closed_pair_has_unmatched_ancestor(
    text: str,
    *,
    scope: tuple[int, int],
    opening_index: int,
    closing_index: int,
) -> bool:
    """Delay an inner rewrite until its still-open authored shell is complete."""

    scope_start, scope_end = scope
    local_opening = opening_index - scope_start
    local_closing = closing_index - scope_start
    pairs = balanced_parenthesis_pairs(text[scope_start:scope_end])
    closed_pair = next(
        (
            pair
            for pair in pairs
            if pair.opening_index == local_opening
            and pair.closing_index == local_closing
        ),
        None,
    )
    if closed_pair is None:
        return False
    balanced_ancestor_count = sum(
        pair.opening_index < local_opening and local_closing < pair.closing_index
        for pair in pairs
    )
    return closed_pair.depth > balanced_ancestor_count + 1


def _containing_segment_scope(
    text: str,
    start: int,
    end: int,
) -> tuple[int, int]:
    """Return the complete parsed segment containing one parenthesis group."""

    for segment in parse_prompt_document(text).segments:
        if segment.content_range.start <= start and end <= segment.content_range.end:
            return segment.content_range.start, segment.content_range.end
    return start, end


def _matching_opening_parenthesis(text: str, *, close_index: int) -> int | None:
    """Return the unescaped opening parenthesis matched by one closing parenthesis."""

    depth = 0
    for index in range(close_index, -1, -1):
        character = text[index]
        if _is_escaped_source_character(text, index):
            continue
        if character == ")":
            depth += 1
            continue
        if character == "(":
            depth -= 1
            if depth == 0:
                return index
    return None


def _matching_closing_parenthesis(text: str, *, open_index: int) -> int | None:
    """Return the unescaped closing parenthesis matched by one opening parenthesis."""

    depth = 0
    for index in range(open_index, len(text)):
        character = text[index]
        if _is_escaped_source_character(text, index):
            continue
        if character == "(":
            depth += 1
            continue
        if character == ")":
            depth -= 1
            if depth == 0:
                return index
    return None


def _is_escaped_source_character(text: str, index: int) -> bool:
    """Return whether a source character is escaped by an odd backslash run."""

    slash_count = 0
    cursor = index - 1
    while cursor >= 0 and text[cursor] == "\\":
        slash_count += 1
        cursor -= 1
    return slash_count % 2 == 1


_TYPED_EMPHASIS_RECLASSIFICATION_CHARACTERS = frozenset(":0123456789.")


__all__ = ["PromptSourceNormalization", "PromptSourceNormalizationService"]

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

"""Build source edits for duplicate-segment diagnostic actions."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from .prompt_diagnostics_models import PromptDuplicateSegmentDiagnosticPayload
from .prompt_duplicate_segment_diagnostic_provider import (
    normalize_duplicate_prompt_segment,
)

_EMPHASIS_STEP = Decimal("0.10")
_NEUTRAL_EMPHASIS_WEIGHT = Decimal("1.00")


@dataclass(frozen=True, slots=True)
class PromptDiagnosticTextEdit:
    """Describe one source replacement for a prompt diagnostic action."""

    source_start: int
    source_end: int
    replacement_text: str


def remove_duplicate_segment_edits(
    source_text: str,
    payload: PromptDuplicateSegmentDiagnosticPayload,
) -> tuple[PromptDiagnosticTextEdit, ...]:
    """Return edits that remove one duplicate segment occurrence cleanly."""

    return (_duplicate_removal_edit(source_text, payload),)


def emphasize_first_duplicate_segment_edits(
    source_text: str,
    payload: PromptDuplicateSegmentDiagnosticPayload,
) -> tuple[PromptDiagnosticTextEdit, ...]:
    """Return edits that remove the duplicate and emphasize the first segment."""

    first_text = source_text[payload.first_source_start : payload.first_source_end]
    duplicate_text = source_text[
        payload.duplicate_source_start : payload.duplicate_source_end
    ]
    emphasized_first = _emphasized_first_text(
        first_text,
        duplicate_text,
        payload.normalized_segment,
    )
    return (
        _duplicate_removal_edit(source_text, payload),
        PromptDiagnosticTextEdit(
            source_start=payload.first_source_start,
            source_end=payload.first_source_end,
            replacement_text=emphasized_first,
        ),
    )


def _duplicate_removal_edit(
    source_text: str,
    payload: PromptDuplicateSegmentDiagnosticPayload,
) -> PromptDiagnosticTextEdit:
    """Return one range replacement that removes an occurrence and its separator."""

    start = payload.duplicate_source_start
    end = payload.duplicate_source_end
    after = end
    while after < len(source_text) and source_text[after] in " \t":
        after += 1
    if after < len(source_text) and source_text[after] == ",":
        after += 1
        while after < len(source_text) and source_text[after] in " \t":
            after += 1
        return PromptDiagnosticTextEdit(start, after, "")

    before = start
    while before > 0 and source_text[before - 1] in " \t":
        before -= 1
    if before > 0 and source_text[before - 1] == ",":
        return PromptDiagnosticTextEdit(before - 1, end, "")

    return PromptDiagnosticTextEdit(start, end, "")


def _emphasized_first_text(
    first_source_text: str,
    duplicate_source_text: str,
    normalized_segment: str,
) -> str:
    """Return first occurrence text with duplicate emphasis transferred."""

    stripped = first_source_text.strip()
    content, first_weight = _unwrap_emphasis_text(stripped)
    duplicate_content, duplicate_weight = _unwrap_emphasis_text(
        duplicate_source_text.strip()
    )
    segment_text = (
        content
        if normalize_duplicate_prompt_segment(content) == normalized_segment
        else stripped
    )
    if normalize_duplicate_prompt_segment(duplicate_content) != normalized_segment:
        duplicate_weight = None
    base_weight = _NEUTRAL_EMPHASIS_WEIGHT if first_weight is None else first_weight
    duplicate_extra_weight = (
        Decimal("0.00")
        if duplicate_weight is None
        else max(Decimal("0.00"), duplicate_weight - _NEUTRAL_EMPHASIS_WEIGHT)
    )
    next_weight = base_weight + _EMPHASIS_STEP + duplicate_extra_weight
    return f"({segment_text}:{next_weight.quantize(Decimal('0.01'))})"


def _unwrap_emphasis_text(source_text: str) -> tuple[str, Decimal | None]:
    """Return emphasis content and optional existing weighted emphasis value."""

    current = source_text
    parsed_weight: Decimal | None = None
    while _is_balanced_parenthesized(current):
        inner = current[1:-1].strip()
        weighted = _split_weighted_emphasis(inner)
        if weighted is not None:
            current, parsed_weight = weighted
            continue
        current = inner
    return current, parsed_weight


def _is_balanced_parenthesized(text: str) -> bool:
    """Return whether text is fully wrapped by one balanced parenthesis pair."""

    if len(text) < 2 or text[0] != "(" or text[-1] != ")":
        return False
    depth = 0
    for index, character in enumerate(text):
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth == 0 and index != len(text) - 1:
                return False
        if depth < 0:
            return False
    return depth == 0


def _split_weighted_emphasis(text: str) -> tuple[str, Decimal] | None:
    """Return content and weight when text uses weighted emphasis syntax."""

    content, separator, raw_weight = text.rpartition(":")
    if not separator or not content or not raw_weight:
        return None
    try:
        weight = Decimal(raw_weight)
    except InvalidOperation:
        return None
    return content.strip(), weight


__all__ = [
    "PromptDiagnosticTextEdit",
    "emphasize_first_duplicate_segment_edits",
    "remove_duplicate_segment_edits",
]

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

"""Normalize completed prompt syntax weights without presentation dependencies."""

from __future__ import annotations

from dataclasses import dataclass

from .models import SourceRange
from .parser import parse_prompt_document
from .weight_formatting import format_prompt_weight


@dataclass(frozen=True, slots=True)
class PromptWeightNormalization:
    """Describe weight-normalized prompt text and original boundary remapping."""

    text: str
    boundary_positions: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class _Replacement:
    """Describe one parsed source range replacement."""

    source_range: SourceRange
    text: str


@dataclass(frozen=True, slots=True)
class _AppliedReplacement:
    """Describe one replacement after assigning normalized text boundaries."""

    source_start: int
    source_end: int
    normalized_start: int
    normalized_end: int


def normalize_prompt_weights(text: str) -> PromptWeightNormalization:
    """Return prompt text with parsed emphasis and LoRA weights fixed to two decimals."""

    replacements = tuple(_weight_replacements_for_document(text))
    if not replacements:
        return PromptWeightNormalization(
            text=text,
            boundary_positions=tuple(range(len(text) + 1)),
        )
    return _apply_replacements(text, replacements)


def _weight_replacements_for_document(text: str) -> tuple[_Replacement, ...]:
    """Return canonical replacements for every parsed weight range in one prompt."""

    document = parse_prompt_document(text)
    replacements: list[_Replacement] = []
    for span in document.emphasis_spans:
        replacements.append(
            _Replacement(
                source_range=span.weight_range,
                text=format_prompt_weight(span.weight),
            )
        )
    for lora_span in document.lora_spans:
        replacements.append(
            _Replacement(
                source_range=lora_span.first_weight_range,
                text=format_prompt_weight(lora_span.first_weight),
            )
        )
        if (
            lora_span.second_weight_range is not None
            and lora_span.second_weight is not None
        ):
            replacements.append(
                _Replacement(
                    source_range=lora_span.second_weight_range,
                    text=format_prompt_weight(lora_span.second_weight),
                )
            )
    return tuple(
        sorted(
            replacements,
            key=lambda replacement: replacement.source_range.start,
        )
    )


def _apply_replacements(
    text: str,
    replacements: tuple[_Replacement, ...],
) -> PromptWeightNormalization:
    """Apply sorted replacements and return full boundary remapping."""

    parts: list[str] = []
    applied_replacements: list[_AppliedReplacement] = []
    source_cursor = 0
    normalized_cursor = 0
    for replacement in replacements:
        unchanged_text = text[source_cursor : replacement.source_range.start]
        parts.append(unchanged_text)
        normalized_cursor += len(unchanged_text)
        normalized_start = normalized_cursor
        parts.append(replacement.text)
        normalized_cursor += len(replacement.text)
        applied_replacements.append(
            _AppliedReplacement(
                source_start=replacement.source_range.start,
                source_end=replacement.source_range.end,
                normalized_start=normalized_start,
                normalized_end=normalized_cursor,
            )
        )
        source_cursor = replacement.source_range.end
    parts.append(text[source_cursor:])
    normalized_text = "".join(parts)
    applied = tuple(applied_replacements)
    return PromptWeightNormalization(
        text=normalized_text,
        boundary_positions=tuple(
            _map_boundary(index, applied) for index in range(len(text) + 1)
        ),
    )


def _map_boundary(
    source_index: int,
    replacements: tuple[_AppliedReplacement, ...],
) -> int:
    """Map one original source boundary into normalized text."""

    delta = 0
    for replacement in replacements:
        if source_index < replacement.source_start:
            return source_index + delta
        if source_index == replacement.source_start:
            return replacement.normalized_start
        if replacement.source_start < source_index < replacement.source_end:
            source_offset = source_index - replacement.source_start
            return min(
                replacement.normalized_end,
                replacement.normalized_start + source_offset,
            )
        if source_index == replacement.source_end:
            return replacement.normalized_end
        delta = replacement.normalized_end - replacement.source_end
    return source_index + delta


__all__ = ["PromptWeightNormalization", "normalize_prompt_weights"]

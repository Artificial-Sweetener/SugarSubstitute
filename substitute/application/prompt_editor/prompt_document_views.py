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

"""Define prompt document view models shared by application and presentation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PromptSegmentView:
    """Expose one parsed prompt segment without leaking domain imports to presentation."""

    index: int
    text: str
    display_text: str
    display_source_start: int
    display_source_end: int
    selection_start: int
    selection_end: int
    separator_text_after: str
    has_separator_after: bool


@dataclass(frozen=True, slots=True)
class PromptReorderChipView:
    """Expose one reorder chip without leaking domain imports to presentation."""

    index: int
    text: str
    serialized_text: str
    display_text: str
    display_source_start: int
    display_source_end: int
    selection_start: int
    selection_end: int
    separator_text_after: str
    has_separator_after: bool


@dataclass(frozen=True, slots=True)
class PromptEmphasisView:
    """Expose one parsed emphasis span to presentation callers."""

    outer_start: int
    outer_end: int
    content_start: int
    content_end: int
    weight_start: int
    weight_end: int
    weight: Decimal
    weight_text: str
    depth: int


@dataclass(frozen=True, slots=True)
class PromptWildcardView:
    """Expose one parsed wildcard span to presentation callers."""

    outer_start: int
    outer_end: int
    content_start: int
    content_end: int
    wildcard_form: str
    identifier: str
    csv_column: str | None
    tag: str | None
    depth: int


@dataclass(frozen=True, slots=True)
class PromptLoraView:
    """Expose one parsed LoRA schedule span to presentation callers."""

    outer_start: int
    outer_end: int
    name_start: int
    name_end: int
    first_weight_start: int
    first_weight_end: int
    first_weight: Decimal
    first_weight_text: str
    second_weight_start: int | None
    second_weight_end: int | None
    second_weight: Decimal | None
    second_weight_text: str | None
    block_weights_start: int | None
    block_weights_end: int | None
    prompt_name: str
    depth: int


@dataclass(frozen=True, slots=True)
class PromptSyntaxSpanView:
    """Describe one prompt syntax span without exposing domain imports."""

    kind: str
    start: int
    end: int
    depth: int


@dataclass(frozen=True, slots=True)
class PromptDocumentView:
    """Expose one immutable prompt snapshot for presentation and application flows."""

    source_text: str
    segments: Sequence[PromptSegmentView]
    emphasis_spans: Sequence[PromptEmphasisView]
    wildcard_spans: Sequence[PromptWildcardView]
    lora_spans: Sequence[PromptLoraView]
    syntax_spans: Sequence[PromptSyntaxSpanView]
    has_trailing_comma: bool


__all__ = [
    "PromptDocumentView",
    "PromptEmphasisView",
    "PromptLoraView",
    "PromptReorderChipView",
    "PromptSegmentView",
    "PromptSyntaxSpanView",
    "PromptWildcardView",
]

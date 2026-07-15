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

"""Define immutable domain models for prompt text structure and mutations."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .syntax import SyntaxKind, WildcardForm


@dataclass(frozen=True, slots=True)
class SourceRange:
    """Represent one half-open source range inside prompt text."""

    start: int
    end: int

    def __post_init__(self) -> None:
        """Reject inverted source ranges."""

        if self.start < 0:
            raise ValueError("SourceRange.start must be non-negative.")
        if self.end < self.start:
            raise ValueError("SourceRange.end must be greater than or equal to start.")

    @property
    def length(self) -> int:
        """Return the number of covered source characters."""

        return self.end - self.start

    def contains(self, position: int, *, inclusive_end: bool = False) -> bool:
        """Return whether the supplied position falls inside this range."""

        if inclusive_end:
            return self.start <= position <= self.end
        return self.start <= position < self.end

    def encloses(self, other: "SourceRange") -> bool:
        """Return whether this range fully contains another range."""

        return self.start <= other.start and self.end >= other.end

    def slice(self, text: str) -> str:
        """Return the covered substring from one source string."""

        return text[self.start : self.end]


@dataclass(frozen=True, slots=True)
class PromptSegment:
    """Represent one comma-delimited prompt segment."""

    index: int
    text: str
    content_range: SourceRange
    separator_range: SourceRange | None = None

    @property
    def display_text(self) -> str:
        """Return the user-facing chip label for this segment."""

        return self.text.strip()

    def separator_text(self, source_text: str) -> str:
        """Return the exact separator text that originally followed this segment."""

        if self.separator_range is None:
            return ""
        return self.separator_range.slice(source_text)

    @property
    def visible_range(self) -> SourceRange:
        """Return the selection range used by current prompt-segment actions."""

        leading_whitespace = len(self.text) - len(self.text.lstrip(" \t"))
        visible_start = min(
            self.content_range.end,
            self.content_range.start + leading_whitespace,
        )
        return SourceRange(visible_start, self.content_range.end)


@dataclass(frozen=True, slots=True)
class SyntaxSpan:
    """Represent one syntax span independent of any renderer."""

    kind: SyntaxKind
    source_range: SourceRange
    depth: int = 0


@dataclass(frozen=True, slots=True)
class EmphasisSpan:
    """Represent one parsed weighted-emphasis construct."""

    outer_range: SourceRange
    content_range: SourceRange
    weight_range: SourceRange
    weight: Decimal
    depth: int = 0

    @property
    def kind(self) -> SyntaxKind:
        """Return the syntax kind for this span."""

        return SyntaxKind.EMPHASIS


@dataclass(frozen=True, slots=True)
class WildcardSpan:
    """Represent one parsed wildcard placeholder construct."""

    outer_range: SourceRange
    content_range: SourceRange
    wildcard_form: WildcardForm
    identifier: str
    csv_column: str | None = None
    tag: str | None = None
    depth: int = 0

    @property
    def kind(self) -> SyntaxKind:
        """Return the syntax kind for this span."""

        return SyntaxKind.WILDCARD


@dataclass(frozen=True, slots=True)
class LoraSpan:
    """Represent one parsed Prompt Control LoRA scheduling construct."""

    outer_range: SourceRange
    name_range: SourceRange
    first_weight_range: SourceRange
    first_weight: Decimal
    second_weight_range: SourceRange | None = None
    second_weight: Decimal | None = None
    block_weights_range: SourceRange | None = None
    depth: int = 0

    @property
    def kind(self) -> SyntaxKind:
        """Return the syntax kind for this span."""

        return SyntaxKind.LORA


@dataclass(frozen=True, slots=True)
class PromptDocument:
    """Represent the parsed prompt document and all prompt-domain spans."""

    source_text: str
    segments: tuple[PromptSegment, ...]
    syntax_spans: tuple[SyntaxSpan, ...]
    emphasis_spans: tuple[EmphasisSpan, ...]
    wildcard_spans: tuple[WildcardSpan, ...]
    lora_spans: tuple[LoraSpan, ...]
    has_trailing_comma: bool = False

    def segment_at_position(self, position: int) -> PromptSegment | None:
        """Return the segment selected by the current legacy cursor rules."""

        for segment in self.segments:
            visible_range = segment.visible_range
            if visible_range.contains(position, inclusive_end=True):
                return segment
        return None

    def emphasis_at_position(self, position: int) -> EmphasisSpan | None:
        """Return the innermost emphasis span matching one cursor position."""

        for span in reversed(self.emphasis_spans):
            if span.content_range.contains(position, inclusive_end=True):
                return span
        for span in reversed(self.emphasis_spans):
            if span.outer_range.start < position < span.outer_range.end:
                return span
        return None

    def emphasis_with_content_range(
        self,
        selection_range: SourceRange,
    ) -> EmphasisSpan | None:
        """Return the emphasis span whose core matches the supplied selection."""

        for span in self.emphasis_spans:
            if span.content_range == selection_range:
                return span
        return None

    def emphasis_with_outer_range(
        self,
        selection_range: SourceRange,
    ) -> EmphasisSpan | None:
        """Return the emphasis span whose full shell matches the supplied selection."""

        for span in self.emphasis_spans:
            if span.outer_range == selection_range:
                return span
        return None

    def lora_with_outer_range(
        self,
        selection_range: SourceRange,
    ) -> LoraSpan | None:
        """Return the LoRA span whose full shell matches the supplied range."""

        for span in self.lora_spans:
            if span.outer_range == selection_range:
                return span
        return None

    def wildcard_with_outer_range(
        self,
        selection_range: SourceRange,
    ) -> WildcardSpan | None:
        """Return the wildcard span whose full placeholder matches the supplied range."""

        for span in self.wildcard_spans:
            if span.outer_range == selection_range:
                return span
        return None


@dataclass(frozen=True, slots=True)
class PromptMutationResult:
    """Return the updated prompt text plus selection restoration data."""

    text: str
    document: PromptDocument
    selection_range: SourceRange | None = None

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

"""Define immutable values shared by prompt reorder operations."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TypeAlias

from substitute.domain.prompt.document.ranges import SourceRange


@dataclass(frozen=True, slots=True)
class PromptReorderEnvelope:
    """Describe one transparent emphasis shell carried by a reorder chip."""

    weight: Decimal
    weight_text: str


@dataclass(frozen=True, slots=True)
class PromptReorderChip:
    """Represent one reorderable chip, including transparent emphasis envelopes."""

    index: int
    partition_index: int
    text: str
    content_range: SourceRange
    separator_range: SourceRange | None
    envelope_stack: tuple[PromptReorderEnvelope, ...] = ()
    leading_text: str = ""
    trailing_text: str = ""

    @property
    def display_text(self) -> str:
        """Return the user-facing label shown on one reorder chip."""

        return self.text.strip()

    def separator_text(self, source_text: str) -> str:
        """Return the exact separator text that originally followed this chip."""

        if self.separator_range is None:
            return ""
        return self.separator_range.slice(source_text)

    @property
    def visible_range(self) -> SourceRange:
        """Return the source range highlighted when the chip is focused or moved."""

        leading_whitespace = len(self.text) - len(self.text.lstrip(" \t"))
        visible_start = min(
            self.content_range.end,
            self.content_range.start + leading_whitespace,
        )
        return SourceRange(visible_start, self.content_range.end)


@dataclass(frozen=True, slots=True)
class PromptReorderSerialization:
    """Return serialized reorder text plus chip and slot range bookkeeping."""

    text: str
    chip_ranges_by_index: dict[int, SourceRange]
    rendered_ranges_by_index: dict[int, SourceRange]
    owned_ranges_by_index: dict[int, tuple[SourceRange, ...]]
    slot_ranges_by_index: dict[int, SourceRange]


@dataclass(frozen=True, slots=True)
class PromptReorderState:
    """Store prompt reorder state as segment order plus separator slots."""

    ordered_segment_indices: tuple[int, ...]
    partition_index_by_segment_index: tuple[int, ...]
    separator_slots: tuple[str, ...]
    has_trailing_comma: bool
    prefix_text: str
    suffix_text: str

    def __post_init__(self) -> None:
        """Reject separator-slot counts that cannot describe the segment order."""

        expected_slot_count = max(0, len(self.ordered_segment_indices) - 1)
        if len(self.separator_slots) != expected_slot_count:
            raise ValueError(
                "PromptReorderState.separator_slots must match the segment order."
            )
        if self.ordered_segment_indices and max(self.ordered_segment_indices) >= len(
            self.partition_index_by_segment_index
        ):
            raise ValueError(
                "PromptReorderState.partition_index_by_segment_index must cover every segment."
            )


@dataclass(frozen=True, slots=True)
class PromptDerivedRow:
    """Describe one derived presentation row inside reorder state."""

    row_index: int
    partition_index: int
    start_segment_offset: int
    segment_indices: tuple[int, ...]
    boundary_separator_before: str


@dataclass(frozen=True, slots=True)
class PromptDerivedGap:
    """Describe one derived multiline separator slot between presentation rows."""

    gap_index: int
    partition_index: int
    slot_index: int
    separator_text: str
    blank_line_offsets: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class PromptLineDropTarget:
    """Insert the dragged segment into one populated row at the supplied position."""

    row_index: int
    insertion_index: int


@dataclass(frozen=True, slots=True)
class PromptGapBlankLineDropTarget:
    """Insert the dragged segment onto one blank line inside a multiline gap."""

    gap_index: int
    blank_line_index: int


PromptReorderDropTarget: TypeAlias = PromptLineDropTarget | PromptGapBlankLineDropTarget


__all__ = [
    "PromptDerivedGap",
    "PromptDerivedRow",
    "PromptGapBlankLineDropTarget",
    "PromptLineDropTarget",
    "PromptReorderChip",
    "PromptReorderDropTarget",
    "PromptReorderEnvelope",
    "PromptReorderSerialization",
    "PromptReorderState",
]

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

"""Define prompt reorder view models shared by application and presentation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TypeAlias

from .prompt_document_views import PromptReorderChipView


@dataclass(frozen=True, slots=True)
class PromptLineDropTarget:
    """Describe one populated-row insertion target for segment reorder preview and commit."""

    row_index: int
    insertion_index: int


@dataclass(frozen=True, slots=True)
class PromptGapBlankLineDropTarget:
    """Describe one blank-line destination inside one logical multiline row gap."""

    gap_index: int
    blank_line_index: int


PromptReorderDropTarget: TypeAlias = PromptLineDropTarget | PromptGapBlankLineDropTarget


@dataclass(frozen=True, slots=True)
class PromptReorderRowView:
    """Expose one logical reorder row without leaking domain imports to presentation."""

    row_index: int
    chip_indices: tuple[int, ...]
    separator_slots: tuple[str, ...] = field(default=(), compare=False)


class PromptReorderGapPlacement(Enum):
    """Describe where a reorder gap sits relative to populated rows."""

    BETWEEN_ROWS = "between_rows"
    AFTER_LAST_ROW = "after_last_row"


@dataclass(frozen=True, slots=True)
class PromptReorderGapView:
    """Expose one logical reorder gap and its blank-line affordances."""

    gap_index: int
    separator_text: str
    blank_line_count: int
    placement: PromptReorderGapPlacement = PromptReorderGapPlacement.BETWEEN_ROWS


@dataclass(frozen=True, slots=True)
class PromptReorderLayoutView:
    """Expose derived reorder rows and multiline gaps for prompt-editor drag preview."""

    rows: tuple[PromptReorderRowView, ...]
    gaps: tuple[PromptReorderGapView, ...]


@dataclass(frozen=True, slots=True)
class PromptReorderStateView:
    """Expose authoritative reorder source state without leaking domain types."""

    ordered_chip_indices: tuple[int, ...]
    separator_slots: tuple[str, ...]
    has_trailing_comma: bool


@dataclass(frozen=True, slots=True)
class PromptReorderSessionView:
    """Expose one reorder-mode snapshot built from a single parsed prompt document."""

    chips: tuple[PromptReorderChipView, ...]
    reorder_state: PromptReorderStateView
    layout_view: PromptReorderLayoutView


@dataclass(frozen=True, slots=True)
class PromptReorderPreviewSnapshot:
    """Expose one serialized preview text snapshot plus chip and gap ranges."""

    text: str
    chip_ranges_by_index: dict[int, tuple[int, int]]
    chip_rendered_ranges_by_index: dict[int, tuple[int, int]]
    chip_owned_ranges_by_index: dict[int, tuple[tuple[int, int], ...]]
    gap_ranges_by_index: dict[int, tuple[int, int]]


__all__ = [
    "PromptGapBlankLineDropTarget",
    "PromptLineDropTarget",
    "PromptReorderDropTarget",
    "PromptReorderGapPlacement",
    "PromptReorderGapView",
    "PromptReorderLayoutView",
    "PromptReorderPreviewSnapshot",
    "PromptReorderRowView",
    "PromptReorderSessionView",
    "PromptReorderStateView",
]

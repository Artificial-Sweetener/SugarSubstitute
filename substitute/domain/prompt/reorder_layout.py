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

"""Define separator-slot prompt reorder semantics and mutations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from .models import PromptDocument, PromptMutationResult, SourceRange
from .parser import parse_prompt_document
from .serializer import normalize_reorder_separator_text


@dataclass(frozen=True, slots=True)
class PromptReorderState:
    """Store prompt reorder state as segment order plus separator slots."""

    ordered_segment_indices: tuple[int, ...]
    separator_slots: tuple[str, ...]
    has_trailing_comma: bool

    def __post_init__(self) -> None:
        """Reject separator-slot counts that cannot describe the segment order."""

        expected_slot_count = max(0, len(self.ordered_segment_indices) - 1)
        if len(self.separator_slots) != expected_slot_count:
            raise ValueError(
                "PromptReorderState.separator_slots must match the segment order."
            )


@dataclass(frozen=True, slots=True)
class PromptDerivedRow:
    """Describe one derived presentation row inside reorder state."""

    row_index: int
    start_segment_offset: int
    segment_indices: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class PromptDerivedGap:
    """Describe one derived multiline separator slot between presentation rows."""

    gap_index: int
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


def build_reorder_state(document: PromptDocument) -> PromptReorderState:
    """Project one parsed prompt document into canonical separator-slot reorder state."""

    ordered_segment_indices = tuple(segment.index for segment in document.segments)
    separator_slots = tuple(
        normalize_reorder_separator_text(segment.separator_text(document.source_text))
        for segment in document.segments[:-1]
    )
    return PromptReorderState(
        ordered_segment_indices=ordered_segment_indices,
        separator_slots=separator_slots,
        has_trailing_comma=document.has_trailing_comma,
    )


def derive_rows_and_gaps(
    state: PromptReorderState,
) -> tuple[tuple[PromptDerivedRow, ...], tuple[PromptDerivedGap, ...]]:
    """Derive presentation rows and multiline gaps from one canonical reorder state."""

    if not state.ordered_segment_indices:
        return (), ()

    rows: list[PromptDerivedRow] = []
    gaps: list[PromptDerivedGap] = []
    current_row_indices: list[int] = []
    current_row_start_offset = 0

    for segment_offset, segment_index in enumerate(state.ordered_segment_indices):
        current_row_indices.append(segment_index)
        if segment_offset >= len(state.separator_slots):
            continue

        separator_text = state.separator_slots[segment_offset]
        if "\n" not in separator_text and "\r" not in separator_text:
            continue

        rows.append(
            PromptDerivedRow(
                row_index=len(rows),
                start_segment_offset=current_row_start_offset,
                segment_indices=tuple(current_row_indices),
            )
        )
        gaps.append(
            PromptDerivedGap(
                gap_index=len(gaps),
                slot_index=segment_offset,
                separator_text=separator_text,
                blank_line_offsets=blank_line_drop_offsets(separator_text),
            )
        )
        current_row_indices = []
        current_row_start_offset = segment_offset + 1

    if current_row_indices:
        rows.append(
            PromptDerivedRow(
                row_index=len(rows),
                start_segment_offset=current_row_start_offset,
                segment_indices=tuple(current_row_indices),
            )
        )

    return tuple(rows), tuple(gaps)


def blank_line_drop_offsets(separator_text: str) -> tuple[int, ...]:
    """Return the separator offsets that begin drawable blank-line drop targets."""

    newline_offsets: list[int] = []
    index = 0
    while index < len(separator_text):
        character = separator_text[index]
        if character == "\r":
            index += (
                2
                if index + 1 < len(separator_text) and separator_text[index + 1] == "\n"
                else 1
            )
            while index < len(separator_text) and separator_text[index] in " \t":
                index += 1
            newline_offsets.append(index)
            continue
        if character == "\n":
            index += 1
            while index < len(separator_text) and separator_text[index] in " \t":
                index += 1
            newline_offsets.append(index)
            continue
        index += 1

    if len(newline_offsets) <= 1:
        return ()
    return tuple(newline_offsets[:-1])


def split_gap_for_blank_line_insert(
    separator_text: str,
    *,
    blank_line_index: int,
) -> tuple[str, str]:
    """Split one multiline gap so an inserted row becomes first on the chosen blank line."""

    offsets = blank_line_drop_offsets(separator_text)
    if not 0 <= blank_line_index < len(offsets):
        raise ValueError(
            "blank_line_index must reference an available blank-line target."
        )

    split_offset = offsets[blank_line_index]
    prefix_separator = separator_text[:split_offset]
    suffix_separator = f",{separator_text[split_offset:]}"
    return prefix_separator, suffix_separator


def build_base_drag_state(
    state: PromptReorderState,
    *,
    dragged_segment_index: int,
) -> PromptReorderState:
    """Return the canonical reorder state while the dragged segment is hidden."""

    if dragged_segment_index not in state.ordered_segment_indices:
        raise ValueError(
            "dragged_segment_index must reference an available prompt segment."
        )

    dragged_offset = state.ordered_segment_indices.index(dragged_segment_index)
    remaining_indices = list(state.ordered_segment_indices)
    remaining_slots = list(state.separator_slots)
    remaining_indices.pop(dragged_offset)

    if not state.separator_slots:
        return PromptReorderState(
            ordered_segment_indices=tuple(remaining_indices),
            separator_slots=(),
            has_trailing_comma=state.has_trailing_comma,
        )

    if dragged_offset == 0:
        del remaining_slots[0]
    elif dragged_offset == len(state.ordered_segment_indices) - 1:
        remaining_slots.pop()
    else:
        remaining_slots[dragged_offset - 1] = _merge_separator_slots(
            remaining_slots[dragged_offset - 1],
            remaining_slots[dragged_offset],
        )
        del remaining_slots[dragged_offset]

    return PromptReorderState(
        ordered_segment_indices=tuple(remaining_indices),
        separator_slots=tuple(remaining_slots),
        has_trailing_comma=state.has_trailing_comma,
    )


def apply_line_drop_target_to_state(
    base_drag_state: PromptReorderState,
    *,
    dragged_segment_index: int,
    target: PromptLineDropTarget,
) -> PromptReorderState:
    """Insert one dragged segment at the supplied populated-row target."""

    rows, _gaps = derive_rows_and_gaps(base_drag_state)
    if not 0 <= target.row_index < len(rows):
        raise ValueError("row_index must reference an available reorder row.")

    destination_row = rows[target.row_index]
    if not 0 <= target.insertion_index <= len(destination_row.segment_indices):
        raise ValueError(
            "insertion_index must reference a valid position inside the row."
        )

    ordered_segment_indices = list(base_drag_state.ordered_segment_indices)
    separator_slots = list(base_drag_state.separator_slots)
    absolute_segment_offset = (
        destination_row.start_segment_offset + target.insertion_index
    )
    ordered_segment_indices.insert(absolute_segment_offset, dragged_segment_index)

    if target.insertion_index == 0:
        separator_slots.insert(
            absolute_segment_offset,
            _default_row_separator(
                base_drag_state,
                row=destination_row,
            ),
        )
    elif target.insertion_index == len(destination_row.segment_indices):
        separator_slots.insert(
            absolute_segment_offset - 1,
            _default_row_separator(
                base_drag_state,
                row=destination_row,
            ),
        )
    else:
        original_slot = separator_slots[absolute_segment_offset - 1]
        separator_slots[absolute_segment_offset - 1] = _default_row_separator(
            base_drag_state,
            row=destination_row,
        )
        separator_slots.insert(absolute_segment_offset, original_slot)

    return PromptReorderState(
        ordered_segment_indices=tuple(ordered_segment_indices),
        separator_slots=tuple(separator_slots),
        has_trailing_comma=base_drag_state.has_trailing_comma,
    )


def apply_blank_line_drop_target_to_state(
    base_drag_state: PromptReorderState,
    *,
    dragged_segment_index: int,
    target: PromptGapBlankLineDropTarget,
) -> PromptReorderState:
    """Insert one dragged segment onto an explicit blank line inside a multiline gap."""

    _rows, gaps = derive_rows_and_gaps(base_drag_state)
    if not 0 <= target.gap_index < len(gaps):
        raise ValueError("gap_index must reference an available reorder gap.")

    targeted_gap = gaps[target.gap_index]
    prefix_separator, suffix_separator = split_gap_for_blank_line_insert(
        targeted_gap.separator_text,
        blank_line_index=target.blank_line_index,
    )

    ordered_segment_indices = list(base_drag_state.ordered_segment_indices)
    separator_slots = list(base_drag_state.separator_slots)
    absolute_segment_offset = targeted_gap.slot_index + 1
    ordered_segment_indices.insert(absolute_segment_offset, dragged_segment_index)
    separator_slots[targeted_gap.slot_index] = prefix_separator
    separator_slots.insert(targeted_gap.slot_index + 1, suffix_separator)

    return PromptReorderState(
        ordered_segment_indices=tuple(ordered_segment_indices),
        separator_slots=tuple(separator_slots),
        has_trailing_comma=base_drag_state.has_trailing_comma,
    )


def apply_drop_target_to_state(
    base_drag_state: PromptReorderState,
    *,
    dragged_segment_index: int,
    target: PromptReorderDropTarget,
) -> PromptReorderState:
    """Dispatch one typed drop target against the separator-slot reorder state."""

    if isinstance(target, PromptLineDropTarget):
        return apply_line_drop_target_to_state(
            base_drag_state,
            dragged_segment_index=dragged_segment_index,
            target=target,
        )
    return apply_blank_line_drop_target_to_state(
        base_drag_state,
        dragged_segment_index=dragged_segment_index,
        target=target,
    )


def serialize_reorder_state(
    state: PromptReorderState,
    *,
    segment_texts_by_index: tuple[str, ...],
) -> str:
    """Serialize one canonical reorder state back into prompt text."""

    serialized_parts: list[str] = []
    for segment_offset, segment_index in enumerate(state.ordered_segment_indices):
        serialized_parts.append(segment_texts_by_index[segment_index])
        if segment_offset < len(state.separator_slots):
            serialized_parts.append(state.separator_slots[segment_offset])

    if state.has_trailing_comma:
        serialized_parts.append(", ")
    return "".join(serialized_parts)


def apply_reorder_drop_target(
    document: PromptDocument,
    *,
    dragged_segment_index: int,
    target: PromptReorderDropTarget,
) -> PromptMutationResult:
    """Apply one typed drop target and return the updated prompt mutation result."""

    reorder_state = build_reorder_state(document)
    base_drag_state = build_base_drag_state(
        reorder_state,
        dragged_segment_index=dragged_segment_index,
    )
    updated_state = apply_drop_target_to_state(
        base_drag_state,
        dragged_segment_index=dragged_segment_index,
        target=target,
    )
    updated_text = serialize_reorder_state(
        updated_state,
        segment_texts_by_index=tuple(segment.text for segment in document.segments),
    )
    updated_document = parse_prompt_document(updated_text)
    selection_range = _selection_range_for_segment(
        updated_document,
        updated_state=updated_state,
        dragged_segment_index=dragged_segment_index,
    )
    return PromptMutationResult(
        text=updated_text,
        document=updated_document,
        selection_range=selection_range,
    )


def _merge_separator_slots(left_slot: str, right_slot: str) -> str:
    """Merge adjacent slots after removing the dragged segment between them."""

    if not right_slot.startswith(","):
        if "\n" in right_slot or "\r" in right_slot:
            if "\n" in left_slot or "\r" in left_slot:
                return normalize_reorder_separator_text(left_slot + right_slot)
            return right_slot
        if "," not in left_slot and "\n" not in left_slot and "\r" not in left_slot:
            return _merge_inline_separator_slots(left_slot, right_slot)
        raise ValueError("Merged separator slots must start with a comma.")
    right_slot_suffix = right_slot[1:]
    if "\n" in left_slot or "\r" in left_slot:
        right_slot_suffix = right_slot_suffix.lstrip(" \t")
    if (
        "\n" not in left_slot
        and "\r" not in left_slot
        and right_slot_suffix
        and right_slot_suffix.strip(" \t") == ""
        and left_slot.endswith((" ", "\t"))
    ):
        return left_slot
    return normalize_reorder_separator_text(left_slot + right_slot_suffix)


def _default_row_separator(
    state: PromptReorderState,
    *,
    row: PromptDerivedRow,
) -> str:
    """Return the same-row separator style already used by one reorder row."""

    start_slot = row.start_segment_offset
    end_slot = start_slot + max(0, len(row.segment_indices) - 1)
    row_slots = state.separator_slots[start_slot:end_slot]
    for slot in row_slots:
        if "," in slot and "\n" not in slot and "\r" not in slot:
            return slot
    if any("\n" in slot or "\r" in slot for slot in row_slots):
        return ", "
    if any(slot for slot in row_slots):
        return " "
    if row_slots:
        return ""
    return ", "


def _merge_inline_separator_slots(left_slot: str, right_slot: str) -> str:
    """Merge adjacent non-comma same-row separators after hiding a chip."""

    if right_slot:
        return right_slot
    return left_slot


def _selection_range_for_segment(
    updated_document: PromptDocument,
    *,
    updated_state: PromptReorderState,
    dragged_segment_index: int,
) -> SourceRange:
    """Return the moved segment's visible range inside the updated prompt document."""

    target_index = updated_state.ordered_segment_indices.index(dragged_segment_index)
    return updated_document.segments[target_index].visible_range


__all__ = [
    "PromptDerivedGap",
    "PromptDerivedRow",
    "PromptGapBlankLineDropTarget",
    "PromptLineDropTarget",
    "PromptReorderDropTarget",
    "PromptReorderState",
    "apply_blank_line_drop_target_to_state",
    "apply_drop_target_to_state",
    "apply_line_drop_target_to_state",
    "apply_reorder_drop_target",
    "blank_line_drop_offsets",
    "build_base_drag_state",
    "build_reorder_state",
    "derive_rows_and_gaps",
    "serialize_reorder_state",
    "split_gap_for_blank_line_insert",
]

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

"""Serialize prompt reorder chips and canonical separator-slot state."""

from __future__ import annotations

from substitute.domain.prompt.document.ranges import SourceRange
from substitute.domain.prompt.reorder.models import (
    PromptReorderChip,
    PromptReorderEnvelope,
    PromptReorderSerialization,
    PromptReorderState,
)


def serialize_reorder_state_for_chips(
    state: PromptReorderState,
    *,
    chips_by_index: tuple[PromptReorderChip, ...],
) -> PromptReorderSerialization:
    """Serialize one chip reorder state while preserving transparent emphasis shells."""

    serialized_parts: list[str] = [state.prefix_text]
    chip_ranges_by_index: dict[int, SourceRange] = {}
    rendered_ranges_by_index: dict[int, SourceRange] = {}
    owned_ranges_by_index: dict[int, tuple[SourceRange, ...]] = {}
    slot_ranges_by_index: dict[int, SourceRange] = {}
    open_envelopes: tuple[PromptReorderEnvelope, ...] = ()
    cursor = len(state.prefix_text)

    for chip_offset, chip_index in enumerate(state.ordered_segment_indices):
        chip = chips_by_index[chip_index]
        shared_prefix_depth = _shared_envelope_prefix_depth(
            open_envelopes,
            chip.envelope_stack,
        )

        for envelope in reversed(open_envelopes[shared_prefix_depth:]):
            closing_text = _closing_text_for_envelope(envelope)
            serialized_parts.append(closing_text)
            cursor += len(closing_text)

        rendered_start = cursor
        if chip.leading_text:
            serialized_parts.append(chip.leading_text)
            cursor += len(chip.leading_text)

        for _envelope in chip.envelope_stack[shared_prefix_depth:]:
            serialized_parts.append("(")
            cursor += 1

        chip_start = cursor
        serialized_parts.append(chip.text)
        cursor += len(chip.text)
        chip_ranges_by_index[chip_index] = SourceRange(chip_start, cursor)

        next_envelopes = (
            ()
            if chip_offset == len(state.ordered_segment_indices) - 1
            else chips_by_index[
                state.ordered_segment_indices[chip_offset + 1]
            ].envelope_stack
        )
        trailing_shared_prefix_depth = _shared_envelope_prefix_depth(
            chip.envelope_stack,
            next_envelopes,
        )

        for envelope in reversed(chip.envelope_stack[trailing_shared_prefix_depth:]):
            closing_text = _closing_text_for_envelope(envelope)
            serialized_parts.append(closing_text)
            cursor += len(closing_text)

        if chip.trailing_text:
            serialized_parts.append(chip.trailing_text)
            cursor += len(chip.trailing_text)
        rendered_range = SourceRange(rendered_start, cursor)
        rendered_ranges_by_index[chip_index] = rendered_range

        open_envelopes = chip.envelope_stack[:trailing_shared_prefix_depth]
        if chip_offset < len(state.separator_slots):
            separator_text = state.separator_slots[chip_offset]
            slot_start = cursor
            serialized_parts.append(separator_text)
            cursor += len(separator_text)
            slot_range = SourceRange(slot_start, cursor)
            slot_ranges_by_index[chip_offset] = slot_range
            owned_ranges_by_index[chip_index] = (rendered_range, slot_range)
            continue

        owned_ranges_by_index[chip_index] = (rendered_range,)

    for envelope in reversed(open_envelopes):
        closing_text = _closing_text_for_envelope(envelope)
        serialized_parts.append(closing_text)
        cursor += len(closing_text)

    if state.has_trailing_comma:
        serialized_parts.append(", ")
    serialized_parts.append(state.suffix_text)

    return PromptReorderSerialization(
        text="".join(serialized_parts),
        chip_ranges_by_index=chip_ranges_by_index,
        rendered_ranges_by_index=rendered_ranges_by_index,
        owned_ranges_by_index=owned_ranges_by_index,
        slot_ranges_by_index=slot_ranges_by_index,
    )


def serialize_reorder_chip(chip: PromptReorderChip) -> str:
    """Serialize one reorder chip as an isolated preview or drag-proxy string."""

    parts: list[str] = []
    if chip.leading_text:
        parts.append(chip.leading_text)
    parts.extend("(" for _envelope in chip.envelope_stack)
    parts.append(chip.text)
    for envelope in reversed(chip.envelope_stack):
        parts.append(_closing_text_for_envelope(envelope))
    if chip.trailing_text:
        parts.append(chip.trailing_text)
    return "".join(parts)


def _shared_envelope_prefix_depth(
    left_stack: tuple[PromptReorderEnvelope, ...],
    right_stack: tuple[PromptReorderEnvelope, ...],
) -> int:
    """Return the common envelope depth shared by two neighboring chips."""

    shared_depth = 0
    for left_envelope, right_envelope in zip(left_stack, right_stack):
        if left_envelope != right_envelope:
            break
        shared_depth += 1
    return shared_depth


def _closing_text_for_envelope(envelope: PromptReorderEnvelope) -> str:
    """Return the serialized closing text for one transparent emphasis envelope."""

    return f":{envelope.weight_text})"


def serialize_reorder_state(
    state: PromptReorderState,
    *,
    segment_texts_by_index: tuple[str, ...],
) -> str:
    """Serialize one canonical reorder state back into prompt text."""

    serialized_parts: list[str] = [state.prefix_text]
    for segment_offset, segment_index in enumerate(state.ordered_segment_indices):
        serialized_parts.append(segment_texts_by_index[segment_index])
        if segment_offset < len(state.separator_slots):
            serialized_parts.append(state.separator_slots[segment_offset])

    if state.has_trailing_comma:
        serialized_parts.append(", ")
    serialized_parts.append(state.suffix_text)
    return "".join(serialized_parts)


__all__ = [
    "serialize_reorder_chip",
    "serialize_reorder_state",
    "serialize_reorder_state_for_chips",
]

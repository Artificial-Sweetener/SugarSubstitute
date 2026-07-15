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

"""Derive and serialize reorder chips without leaking presentation concerns."""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal

from .models import EmphasisSpan, LoraSpan, PromptDocument, PromptSegment, SourceRange
from .parser import parse_prompt_document
from .reorder_layout import PromptReorderState
from .serializer import normalize_reorder_separator_text


@dataclass(frozen=True, slots=True)
class PromptReorderEnvelope:
    """Describe one transparent emphasis shell carried by a reorder chip."""

    weight: Decimal
    weight_text: str


@dataclass(frozen=True, slots=True)
class PromptReorderChip:
    """Represent one reorderable chip, including transparent emphasis envelopes."""

    index: int
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


def build_reorder_chips(document: PromptDocument) -> tuple[PromptReorderChip, ...]:
    """Derive reorder chips from the parsed prompt document."""

    loras_by_segment_index = _lora_spans_by_segment(document)
    raw_chips: list[PromptReorderChip] = []
    for segment in document.segments:
        raw_chips.extend(
            _expand_segment_to_reorder_chips(
                document,
                segment=segment,
                inherited_envelopes=(),
                lora_spans=loras_by_segment_index.get(segment.index, ()),
            )
        )

    return tuple(replace(chip, index=index) for index, chip in enumerate(raw_chips))


def build_reorder_state_from_chips(
    document: PromptDocument,
    chips: tuple[PromptReorderChip, ...],
) -> PromptReorderState:
    """Project reorder chips into the canonical separator-slot state."""

    return PromptReorderState(
        ordered_segment_indices=tuple(chip.index for chip in chips),
        separator_slots=tuple(
            normalize_reorder_separator_text(chip.separator_text(document.source_text))
            for chip in chips[:-1]
        ),
        has_trailing_comma=document.has_trailing_comma,
    )


def serialize_reorder_state_for_chips(
    state: PromptReorderState,
    *,
    chips_by_index: tuple[PromptReorderChip, ...],
) -> PromptReorderSerialization:
    """Serialize one chip reorder state while preserving transparent emphasis shells."""

    serialized_parts: list[str] = []
    chip_ranges_by_index: dict[int, SourceRange] = {}
    rendered_ranges_by_index: dict[int, SourceRange] = {}
    owned_ranges_by_index: dict[int, tuple[SourceRange, ...]] = {}
    slot_ranges_by_index: dict[int, SourceRange] = {}
    open_envelopes: tuple[PromptReorderEnvelope, ...] = ()
    cursor = 0

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


def _expand_segment_to_reorder_chips(
    document: PromptDocument,
    *,
    segment: PromptSegment,
    inherited_envelopes: tuple[PromptReorderEnvelope, ...],
    lora_spans: tuple[LoraSpan, ...],
) -> list[PromptReorderChip]:
    """Expand one parsed segment into reorder chips when it is a chip-spanning shell."""

    segment_display_range = _display_range_for_text(
        text=document.source_text,
        content_range=segment.content_range,
    )
    matching_shell = _matching_emphasis_shell(
        document.emphasis_spans,
        expected_outer_range=segment_display_range,
    )
    if matching_shell is None:
        hard_line_chips = _expand_hard_line_segment_to_reorder_chips(
            document,
            segment=segment,
            inherited_envelopes=inherited_envelopes,
        )
        if hard_line_chips is not None:
            return _expand_reorder_chips_around_loras(
                document,
                chips=hard_line_chips,
                lora_spans=lora_spans,
            )
        fallback_chip = PromptReorderChip(
            index=-1,
            text=segment.text,
            content_range=segment.content_range,
            separator_range=segment.separator_range,
            envelope_stack=inherited_envelopes,
        )
        return _expand_reorder_chip_around_loras(
            document,
            chip=fallback_chip,
            lora_spans=lora_spans,
        )

    nested_document = parse_prompt_document(
        matching_shell.content_range.slice(document.source_text)
    )
    if nested_document.has_trailing_comma or (
        len(nested_document.segments) <= 1 and not lora_spans
    ):
        return [
            PromptReorderChip(
                index=-1,
                text=segment.text,
                content_range=segment.content_range,
                separator_range=segment.separator_range,
                envelope_stack=inherited_envelopes,
            )
        ]

    envelope = PromptReorderEnvelope(
        weight=matching_shell.weight,
        weight_text=matching_shell.weight_range.slice(document.source_text),
    )
    expanded_children: list[PromptReorderChip] = []
    child_offset = matching_shell.content_range.start
    for child_segment in nested_document.segments:
        offset_child_segment = _offset_segment(
            child_segment,
            offset=child_offset,
        )
        expanded_children.extend(
            _expand_segment_to_reorder_chips(
                document,
                segment=offset_child_segment,
                inherited_envelopes=inherited_envelopes + (envelope,),
                lora_spans=_lora_spans_contained_by_range(
                    lora_spans,
                    offset_child_segment.content_range,
                ),
            )
        )

    if not expanded_children:
        return [
            PromptReorderChip(
                index=-1,
                text=segment.text,
                content_range=segment.content_range,
                separator_range=segment.separator_range,
                envelope_stack=inherited_envelopes,
            )
        ]

    outer_leading_text = document.source_text[
        segment.content_range.start : segment_display_range.start
    ]
    outer_trailing_text = document.source_text[
        segment_display_range.end : segment.content_range.end
    ]
    expanded_children[0] = replace(
        expanded_children[0],
        leading_text=outer_leading_text + expanded_children[0].leading_text,
    )
    expanded_children[-1] = replace(
        expanded_children[-1],
        trailing_text=expanded_children[-1].trailing_text + outer_trailing_text,
        separator_range=segment.separator_range,
    )
    return expanded_children


def _expand_hard_line_segment_to_reorder_chips(
    document: PromptDocument,
    *,
    segment: PromptSegment,
    inherited_envelopes: tuple[PromptReorderEnvelope, ...],
) -> list[PromptReorderChip] | None:
    """Split one comma segment at hard line breaks for reorder chip ownership."""

    if "\n" not in segment.text and "\r" not in segment.text:
        return None

    chips: list[PromptReorderChip] = []
    source_text = document.source_text
    line_start = segment.content_range.start
    segment_end = segment.content_range.end
    while line_start < segment_end:
        line_end, break_end = _next_hard_line_bounds(
            source_text,
            start=line_start,
            end=segment_end,
        )
        line_text = source_text[line_start:line_end]
        line_has_visible_text = bool(line_text.strip(" \t"))
        if line_has_visible_text:
            separator_range = (
                SourceRange(line_end, break_end)
                if break_end > line_end
                else segment.separator_range
            )
            chips.append(
                PromptReorderChip(
                    index=-1,
                    text=line_text,
                    content_range=SourceRange(line_start, line_end),
                    separator_range=separator_range,
                    envelope_stack=inherited_envelopes,
                )
            )
        elif chips and break_end > line_end:
            chips[-1] = _with_extended_separator(chips[-1], break_end=break_end)

        if break_end <= line_end:
            break
        line_start = break_end

    if chips and chips[-1].separator_range is None:
        chips[-1] = replace(chips[-1], separator_range=segment.separator_range)
    return chips


def _expand_reorder_chips_around_loras(
    document: PromptDocument,
    *,
    chips: list[PromptReorderChip],
    lora_spans: tuple[LoraSpan, ...],
) -> list[PromptReorderChip]:
    """Split each existing chip around LoRA ranges it contains."""

    expanded_chips: list[PromptReorderChip] = []
    for chip in chips:
        expanded_chips.extend(
            _expand_reorder_chip_around_loras(
                document,
                chip=chip,
                lora_spans=_lora_spans_contained_by_range(
                    lora_spans,
                    chip.content_range,
                ),
            )
        )
    return expanded_chips


def _expand_reorder_chip_around_loras(
    document: PromptDocument,
    *,
    chip: PromptReorderChip,
    lora_spans: tuple[LoraSpan, ...],
) -> list[PromptReorderChip]:
    """Split one reorder chip into text and exact-source LoRA child chips."""

    eligible_loras = _outermost_non_overlapping_lora_spans(lora_spans)
    if not eligible_loras:
        return [chip]

    source_text = document.source_text
    child_chips: list[PromptReorderChip] = []
    cursor = chip.content_range.start
    for lora_span in eligible_loras:
        _append_text_reorder_chip_if_visible(
            child_chips,
            source_text=source_text,
            content_range=SourceRange(cursor, lora_span.outer_range.start),
            next_content_start=lora_span.outer_range.start,
            envelope_stack=chip.envelope_stack,
        )
        child_chips.append(
            PromptReorderChip(
                index=-1,
                text=lora_span.outer_range.slice(source_text),
                content_range=lora_span.outer_range,
                separator_range=None,
                envelope_stack=chip.envelope_stack,
            )
        )
        cursor = lora_span.outer_range.end

    _append_text_reorder_chip_if_visible(
        child_chips,
        source_text=source_text,
        content_range=SourceRange(cursor, chip.content_range.end),
        next_content_start=chip.content_range.end,
        envelope_stack=chip.envelope_stack,
    )
    if not child_chips:
        return [chip]

    for index, child_chip in enumerate(child_chips[:-1]):
        next_chip = child_chips[index + 1]
        child_chips[index] = replace(
            child_chip,
            separator_range=SourceRange(
                child_chip.content_range.end,
                next_chip.content_range.start,
            ),
        )
    child_chips[-1] = replace(child_chips[-1], separator_range=chip.separator_range)
    child_chips[0] = replace(
        child_chips[0],
        leading_text=chip.leading_text + child_chips[0].leading_text,
    )
    child_chips[-1] = replace(
        child_chips[-1],
        trailing_text=child_chips[-1].trailing_text + chip.trailing_text,
    )
    return child_chips


def _append_text_reorder_chip_if_visible(
    chips: list[PromptReorderChip],
    *,
    source_text: str,
    content_range: SourceRange,
    next_content_start: int,
    envelope_stack: tuple[PromptReorderEnvelope, ...],
) -> None:
    """Append a text child chip when one split range has visible text."""

    trimmed_range = _trim_horizontal_whitespace_range(source_text, content_range)
    if trimmed_range is None:
        return
    chips.append(
        PromptReorderChip(
            index=-1,
            text=trimmed_range.slice(source_text),
            content_range=trimmed_range,
            separator_range=SourceRange(trimmed_range.end, next_content_start),
            envelope_stack=envelope_stack,
        )
    )


def _trim_horizontal_whitespace_range(
    text: str,
    source_range: SourceRange,
) -> SourceRange | None:
    """Return the non-horizontal-whitespace content range inside one range."""

    start = source_range.start
    end = source_range.end
    while start < end and text[start] in " \t":
        start += 1
    while end > start and text[end - 1] in " \t":
        end -= 1
    if start == end:
        return None
    return SourceRange(start, end)


def _lora_spans_by_segment(
    document: PromptDocument,
) -> dict[int, tuple[LoraSpan, ...]]:
    """Group parsed LoRA spans by containing comma segment in one ordered pass."""

    grouped_loras: dict[int, list[LoraSpan]] = {}
    lora_index = 0
    lora_spans = document.lora_spans
    for segment in document.segments:
        while (
            lora_index < len(lora_spans)
            and lora_spans[lora_index].outer_range.end <= segment.content_range.start
        ):
            lora_index += 1
        scan_index = lora_index
        while (
            scan_index < len(lora_spans)
            and lora_spans[scan_index].outer_range.start < segment.content_range.end
        ):
            lora_span = lora_spans[scan_index]
            if segment.content_range.encloses(lora_span.outer_range):
                grouped_loras.setdefault(segment.index, []).append(lora_span)
            scan_index += 1
    return {
        segment_index: _outermost_non_overlapping_lora_spans(tuple(segment_loras))
        for segment_index, segment_loras in grouped_loras.items()
    }


def _lora_spans_contained_by_range(
    lora_spans: tuple[LoraSpan, ...],
    content_range: SourceRange,
) -> tuple[LoraSpan, ...]:
    """Return LoRA spans fully contained by one source range."""

    return tuple(
        lora_span
        for lora_span in lora_spans
        if content_range.encloses(lora_span.outer_range)
    )


def _outermost_non_overlapping_lora_spans(
    lora_spans: tuple[LoraSpan, ...],
) -> tuple[LoraSpan, ...]:
    """Return source-ordered LoRA spans safe for independent chip subdivision."""

    outermost_spans: list[LoraSpan] = []
    active_end = -1
    for lora_span in sorted(
        lora_spans,
        key=lambda span: (span.outer_range.start, -span.outer_range.end),
    ):
        if lora_span.outer_range.start < active_end:
            continue
        outermost_spans.append(lora_span)
        active_end = lora_span.outer_range.end
    return tuple(outermost_spans)


def _next_hard_line_bounds(
    text: str,
    *,
    start: int,
    end: int,
) -> tuple[int, int]:
    """Return content and line-break bounds for the next hard source line."""

    index = start
    while index < end:
        character = text[index]
        if character == "\r":
            break_end = index + 1
            if break_end < end and text[break_end] == "\n":
                break_end += 1
            return index, break_end
        if character == "\n":
            return index, index + 1
        index += 1
    return end, end


def _with_extended_separator(
    chip: PromptReorderChip,
    *,
    break_end: int,
) -> PromptReorderChip:
    """Return one chip whose separator owns an additional hard-line break."""

    separator_range = chip.separator_range
    if separator_range is None:
        separator_range = SourceRange(chip.content_range.end, break_end)
    else:
        separator_range = SourceRange(separator_range.start, break_end)
    return replace(chip, separator_range=separator_range)


def _display_range_for_text(*, text: str, content_range: SourceRange) -> SourceRange:
    """Return the stripped display range inside one raw content range."""

    segment_text = content_range.slice(text)
    leading_whitespace = len(segment_text) - len(segment_text.lstrip(" \t"))
    trailing_whitespace = len(segment_text) - len(segment_text.rstrip(" \t"))
    display_start = min(content_range.end, content_range.start + leading_whitespace)
    display_end = max(display_start, content_range.end - trailing_whitespace)
    return SourceRange(display_start, display_end)


def _matching_emphasis_shell(
    emphasis_spans: tuple[EmphasisSpan, ...],
    *,
    expected_outer_range: SourceRange,
) -> EmphasisSpan | None:
    """Return the exact emphasis shell that owns one stripped segment display range."""

    for span in emphasis_spans:
        if span.outer_range == expected_outer_range:
            return span
    return None


def _offset_segment(segment: PromptSegment, *, offset: int) -> PromptSegment:
    """Offset one nested parsed segment back into the original source coordinates."""

    separator_range = (
        None
        if segment.separator_range is None
        else SourceRange(
            segment.separator_range.start + offset,
            segment.separator_range.end + offset,
        )
    )
    return PromptSegment(
        index=segment.index,
        text=segment.text,
        content_range=SourceRange(
            segment.content_range.start + offset,
            segment.content_range.end + offset,
        ),
        separator_range=separator_range,
    )


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


__all__ = [
    "PromptReorderChip",
    "PromptReorderEnvelope",
    "PromptReorderSerialization",
    "build_reorder_chips",
    "build_reorder_state_from_chips",
    "serialize_reorder_chip",
    "serialize_reorder_state_for_chips",
]

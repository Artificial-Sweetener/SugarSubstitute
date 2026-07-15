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

"""Apply deterministic prompt-domain mutations without widget dependencies."""

from __future__ import annotations

from decimal import Decimal

from .models import (
    EmphasisSpan,
    LoraSpan,
    PromptDocument,
    PromptMutationResult,
    SourceRange,
)
from .parser import parse_prompt_document
from .reorder_chips import (
    build_reorder_chips,
    build_reorder_state_from_chips,
    serialize_reorder_state_for_chips,
)
from .reorder_layout import (
    PromptReorderDropTarget,
    apply_drop_target_to_state,
    build_base_drag_state,
)
from .weight_formatting import PROMPT_WEIGHT_PRECISION, format_prompt_weight
from .emphasis_semantics import (
    EDITOR_DEFAULT_POSITIVE_EMPHASIS,
    EDITOR_EMPHASIS_ADJUSTMENT_STEP,
)

_DEFAULT_INCREASE_STEP = EDITOR_EMPHASIS_ADJUSTMENT_STEP
_DEFAULT_DECREASE_STEP = EDITOR_EMPHASIS_ADJUSTMENT_STEP
_MINIMUM_EMPHASIS_WEIGHT = Decimal("0.05")
_NEUTRAL_EMPHASIS_WEIGHT = Decimal("1.00")
_DEFAULT_POSITIVE_WEIGHT = EDITOR_DEFAULT_POSITIVE_EMPHASIS
_DEFAULT_NEGATIVE_WEIGHT = Decimal("0.95")


def reorder_segments(
    document: PromptDocument,
    *,
    dragged_segment_index: int,
    drop_target: PromptReorderDropTarget,
) -> PromptMutationResult:
    """Reorder prompt chips through one typed row/gap drop target."""

    reorder_chips = build_reorder_chips(document)
    reorder_state = build_reorder_state_from_chips(document, reorder_chips)
    base_drag_state = build_base_drag_state(
        reorder_state,
        dragged_segment_index=dragged_segment_index,
    )
    updated_state = apply_drop_target_to_state(
        base_drag_state,
        dragged_segment_index=dragged_segment_index,
        target=drop_target,
    )
    serialization = serialize_reorder_state_for_chips(
        updated_state,
        chips_by_index=reorder_chips,
    )
    updated_document = parse_prompt_document(serialization.text)
    selection_range = serialization.chip_ranges_by_index.get(dragged_segment_index)
    return PromptMutationResult(
        text=serialization.text,
        document=updated_document,
        selection_range=selection_range,
    )


def increase_emphasis(
    document: PromptDocument,
    selection_range: SourceRange,
    *,
    step: Decimal = _DEFAULT_INCREASE_STEP,
) -> PromptMutationResult:
    """Increase emphasis on the selected text or existing emphasis span."""

    return _adjust_emphasis(document, selection_range=selection_range, delta=step)


def decrease_emphasis(
    document: PromptDocument,
    selection_range: SourceRange,
    *,
    step: Decimal = _DEFAULT_DECREASE_STEP,
) -> PromptMutationResult:
    """Decrease emphasis on the selected text or existing emphasis span."""

    return _adjust_emphasis(document, selection_range=selection_range, delta=-step)


def set_emphasis_weight(
    document: PromptDocument,
    selection_range: SourceRange,
    *,
    weight: Decimal,
) -> PromptMutationResult:
    """Set emphasis to one exact weight over an existing shell or plain selection."""

    normalized_range = selection_range
    shell_span = document.emphasis_with_outer_range(selection_range)
    if shell_span is not None:
        normalized_range = shell_span.content_range

    matched_span = document.emphasis_with_content_range(normalized_range)
    normalized_weight = _normalized_emphasis_weight(weight)
    if matched_span is not None:
        return _set_existing_emphasis_weight(
            document,
            span=matched_span,
            weight=normalized_weight,
        )

    if normalized_range.length == 0:
        return _noop_mutation(document, selection_range=normalized_range)
    if normalized_weight == _NEUTRAL_EMPHASIS_WEIGHT:
        return _noop_mutation(document, selection_range=normalized_range)

    return _wrap_plain_selection_with_exact_weight(
        document,
        selection_range=normalized_range,
        weight=normalized_weight,
    )


def adjust_lora_weight(
    document: PromptDocument,
    span: LoraSpan,
    *,
    delta: Decimal,
) -> PromptMutationResult:
    """Adjust the first numeric weight on one parsed LoRA schedule token."""

    return _set_existing_lora_weight(
        document,
        span=span,
        weight=span.first_weight + delta,
    )


def set_lora_weight(
    document: PromptDocument,
    span: LoraSpan,
    *,
    weight: Decimal,
) -> PromptMutationResult:
    """Set the first numeric weight on one parsed LoRA schedule token."""

    return _set_existing_lora_weight(document, span=span, weight=weight)


def unwrap_neutral_emphasis(
    document: PromptDocument,
    span: EmphasisSpan,
) -> PromptMutationResult:
    """Remove the emphasis shell around one weighted span."""

    content_text = span.content_range.slice(document.source_text)
    updated_text = (
        document.source_text[: span.outer_range.start]
        + content_text
        + document.source_text[span.outer_range.end :]
    )
    updated_document = parse_prompt_document(updated_text)
    selection_range = SourceRange(
        span.outer_range.start,
        span.outer_range.start + len(content_text),
    )
    return PromptMutationResult(
        text=updated_text,
        document=updated_document,
        selection_range=selection_range,
    )


def replace_span_content(
    document: PromptDocument,
    span: EmphasisSpan,
    replacement_text: str,
) -> PromptMutationResult:
    """Replace the inner content of one emphasis span."""

    updated_text = (
        document.source_text[: span.content_range.start]
        + replacement_text
        + document.source_text[span.content_range.end :]
    )
    updated_document = parse_prompt_document(updated_text)
    selection_range = SourceRange(
        span.content_range.start,
        span.content_range.start + len(replacement_text),
    )
    return PromptMutationResult(
        text=updated_text,
        document=updated_document,
        selection_range=selection_range,
    )


def _adjust_emphasis(
    document: PromptDocument,
    *,
    selection_range: SourceRange,
    delta: Decimal,
) -> PromptMutationResult:
    """Adjust emphasis around one selected range using deterministic formatting."""

    normalized_range = selection_range
    shell_span = document.emphasis_with_outer_range(selection_range)
    if shell_span is not None:
        normalized_range = shell_span.content_range

    matched_span = document.emphasis_with_content_range(normalized_range)
    if matched_span is not None:
        return _adjust_existing_emphasis(document, span=matched_span, delta=delta)

    if normalized_range.length == 0:
        return PromptMutationResult(
            text=document.source_text,
            document=document,
            selection_range=normalized_range,
        )

    return _wrap_plain_selection(
        document,
        selection_range=normalized_range,
        delta=delta,
    )


def _adjust_existing_emphasis(
    document: PromptDocument,
    *,
    span: EmphasisSpan,
    delta: Decimal,
) -> PromptMutationResult:
    """Adjust the numeric weight on one already-weighted emphasis span."""

    adjusted_weight = _normalized_emphasis_weight(span.weight + delta)
    if adjusted_weight == _NEUTRAL_EMPHASIS_WEIGHT:
        return unwrap_neutral_emphasis(document, span)

    formatted_weight = _format_weight(adjusted_weight)
    updated_text = (
        document.source_text[: span.weight_range.start]
        + formatted_weight
        + document.source_text[span.weight_range.end :]
    )
    updated_document = parse_prompt_document(updated_text)
    updated_span = updated_document.emphasis_with_content_range(span.content_range)
    selection_range = (
        updated_span.content_range if updated_span is not None else span.content_range
    )
    return PromptMutationResult(
        text=updated_text,
        document=updated_document,
        selection_range=selection_range,
    )


def _set_existing_emphasis_weight(
    document: PromptDocument,
    *,
    span: EmphasisSpan,
    weight: Decimal,
) -> PromptMutationResult:
    """Set one existing emphasis shell to the supplied exact numeric weight."""

    if weight == _NEUTRAL_EMPHASIS_WEIGHT:
        return unwrap_neutral_emphasis(document, span)
    formatted_weight = _format_weight(weight)
    updated_text = (
        document.source_text[: span.weight_range.start]
        + formatted_weight
        + document.source_text[span.weight_range.end :]
    )
    updated_document = parse_prompt_document(updated_text)
    updated_span = updated_document.emphasis_with_content_range(span.content_range)
    selection_range = (
        updated_span.content_range if updated_span is not None else span.content_range
    )
    return PromptMutationResult(
        text=updated_text,
        document=updated_document,
        selection_range=selection_range,
    )


def _set_existing_lora_weight(
    document: PromptDocument,
    *,
    span: LoraSpan,
    weight: Decimal,
) -> PromptMutationResult:
    """Set one existing LoRA schedule token's first weight."""

    formatted_weight = _format_weight(weight)
    updated_text = (
        document.source_text[: span.first_weight_range.start]
        + formatted_weight
        + document.source_text[span.first_weight_range.end :]
    )
    updated_document = parse_prompt_document(updated_text)
    selection_range = SourceRange(
        span.first_weight_range.start,
        span.first_weight_range.start + len(formatted_weight),
    )
    return PromptMutationResult(
        text=updated_text,
        document=updated_document,
        selection_range=selection_range,
    )


def _wrap_plain_selection(
    document: PromptDocument,
    *,
    selection_range: SourceRange,
    delta: Decimal,
) -> PromptMutationResult:
    """Wrap plain selected text in a new weighted emphasis shell."""

    selected_text = selection_range.slice(document.source_text)
    default_weight = (
        _DEFAULT_POSITIVE_WEIGHT if delta >= Decimal("0") else _DEFAULT_NEGATIVE_WEIGHT
    )
    replacement_text = f"({selected_text}:{_format_weight(default_weight)})"
    updated_text = (
        document.source_text[: selection_range.start]
        + replacement_text
        + document.source_text[selection_range.end :]
    )
    updated_document = parse_prompt_document(updated_text)
    wrapped_selection = SourceRange(
        selection_range.start + 1,
        selection_range.start + 1 + len(selected_text),
    )
    return PromptMutationResult(
        text=updated_text,
        document=updated_document,
        selection_range=wrapped_selection,
    )


def _wrap_plain_selection_with_exact_weight(
    document: PromptDocument,
    *,
    selection_range: SourceRange,
    weight: Decimal,
) -> PromptMutationResult:
    """Wrap one plain selection in a new exact-weight emphasis shell."""

    selected_text = selection_range.slice(document.source_text)
    replacement_text = f"({selected_text}:{_format_weight(weight)})"
    updated_text = (
        document.source_text[: selection_range.start]
        + replacement_text
        + document.source_text[selection_range.end :]
    )
    updated_document = parse_prompt_document(updated_text)
    wrapped_selection = SourceRange(
        selection_range.start + 1,
        selection_range.start + 1 + len(selected_text),
    )
    return PromptMutationResult(
        text=updated_text,
        document=updated_document,
        selection_range=wrapped_selection,
    )


def _normalized_emphasis_weight(weight: Decimal) -> Decimal:
    """Clamp one emphasis weight to the supported floor while preserving neutral unwrap."""

    if weight < _MINIMUM_EMPHASIS_WEIGHT:
        return _MINIMUM_EMPHASIS_WEIGHT
    return weight.quantize(PROMPT_WEIGHT_PRECISION)


def _noop_mutation(
    document: PromptDocument,
    *,
    selection_range: SourceRange,
) -> PromptMutationResult:
    """Return one no-op mutation that preserves the supplied selection range."""

    return PromptMutationResult(
        text=document.source_text,
        document=document,
        selection_range=selection_range,
    )


def _format_weight(weight: Decimal) -> str:
    """Format one emphasis weight using canonical two-decimal output."""

    return format_prompt_weight(weight)


__all__ = [
    "decrease_emphasis",
    "adjust_lora_weight",
    "increase_emphasis",
    "reorder_segments",
    "replace_span_content",
    "set_emphasis_weight",
    "set_lora_weight",
    "unwrap_neutral_emphasis",
]

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

"""Shift unaffected LoRA syntax views across bounded source edits."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from substitute.application.prompt_editor.document.views import PromptLoraView
from substitute.application.prompt_editor.projection.syntax_models import (
    PromptLoraRendererSpanView,
)

from .source_shifted_sequence import remap_source_sequence


def remap_lora_views_for_edit(
    spans: Sequence[PromptLoraView],
    *,
    start: int,
    end: int,
    delta: int,
) -> Sequence[PromptLoraView]:
    """Return LoRA spans that remain valid after one source edit."""

    return remap_source_sequence(
        spans,
        start=start,
        end=end,
        delta=delta,
        source_range=_view_range,
        shift_item=_shift_view,
    )


def remap_lora_renderer_spans_for_edit(
    spans: Sequence[PromptLoraRendererSpanView],
    *,
    start: int,
    end: int,
    delta: int,
) -> Sequence[PromptLoraRendererSpanView]:
    """Return LoRA renderer spans that remain valid after one source edit."""

    return remap_source_sequence(
        spans,
        start=start,
        end=end,
        delta=delta,
        source_range=_renderer_range,
        shift_item=_shift_renderer_span,
    )


def _view_range(span: PromptLoraView) -> tuple[int, int]:
    """Return one LoRA view's outer source range."""

    return span.outer_start, span.outer_end


def _shift_view(span: PromptLoraView, delta: int) -> PromptLoraView:
    """Shift one unchanged LoRA view by a uniform source delta."""

    return replace(
        span,
        outer_start=span.outer_start + delta,
        outer_end=span.outer_end + delta,
        name_start=span.name_start + delta,
        name_end=span.name_end + delta,
        first_weight_start=span.first_weight_start + delta,
        first_weight_end=span.first_weight_end + delta,
        second_weight_start=_shift_optional(span.second_weight_start, delta),
        second_weight_end=_shift_optional(span.second_weight_end, delta),
        block_weights_start=_shift_optional(span.block_weights_start, delta),
        block_weights_end=_shift_optional(span.block_weights_end, delta),
    )


def _renderer_range(span: PromptLoraRendererSpanView) -> tuple[int, int]:
    """Return one LoRA renderer span's outer source range."""

    return span.outer_start, span.outer_end


def _shift_renderer_span(
    span: PromptLoraRendererSpanView, delta: int
) -> PromptLoraRendererSpanView:
    """Shift one LoRA renderer span by a uniform source delta."""

    return replace(
        span,
        outer_start=span.outer_start + delta,
        outer_end=span.outer_end + delta,
        name_start=span.name_start + delta,
        name_end=span.name_end + delta,
        first_weight_start=span.first_weight_start + delta,
        first_weight_end=span.first_weight_end + delta,
        second_weight_start=_shift_optional(span.second_weight_start, delta),
        second_weight_end=_shift_optional(span.second_weight_end, delta),
    )


def _shift_optional(position: int | None, delta: int) -> int | None:
    """Shift an optional LoRA weight source boundary."""

    return None if position is None else position + delta


__all__ = ["remap_lora_renderer_spans_for_edit", "remap_lora_views_for_edit"]

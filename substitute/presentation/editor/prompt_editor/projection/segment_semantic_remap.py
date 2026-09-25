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

"""Shift source-backed prompt segment views across bounded edits."""

from __future__ import annotations

from collections.abc import Sequence

from substitute.application.prompt_editor.document.views import PromptSegmentView

from .source_shifted_sequence import remap_source_sequence


def remap_segment_views_for_edit(
    segments: Sequence[PromptSegmentView],
    *,
    start: int,
    end: int,
    delta: int,
) -> Sequence[PromptSegmentView]:
    """Return segment ranges that remain valid after one source edit."""

    return remap_source_sequence(
        segments,
        start=start,
        end=end,
        delta=delta,
        source_range=_source_range,
        shift_item=_shift_segment,
    )


def _source_range(segment: PromptSegmentView) -> tuple[int, int]:
    """Return one segment's selection range for lazy remapping."""

    return segment.selection_start, segment.selection_end


def _shift_segment(segment: PromptSegmentView, delta: int) -> PromptSegmentView:
    """Return one unchanged segment shifted by a uniform source delta."""

    return PromptSegmentView(
        index=segment.index,
        text=segment.text,
        display_text=segment.display_text,
        display_source_start=segment.display_source_start + delta,
        display_source_end=segment.display_source_end + delta,
        selection_start=segment.selection_start + delta,
        selection_end=segment.selection_end + delta,
        separator_text_after=segment.separator_text_after,
        has_separator_after=segment.has_separator_after,
    )


__all__ = ["remap_segment_views_for_edit"]

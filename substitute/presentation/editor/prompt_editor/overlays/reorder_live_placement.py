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

"""Validate live-source gap ranges used for provisional drag placement."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.application.prompt_editor.document.views import PromptReorderChipView
from substitute.application.prompt_editor.reorder.views import (
    PromptReorderGapPlacement,
    PromptReorderLayoutView,
)


def live_gap_ranges_for_layout(
    source_text: str,
    layout_view: PromptReorderLayoutView,
    chips_by_index: Mapping[int, PromptReorderChipView],
) -> dict[int, tuple[int, int]] | None:
    """Return verified source ranges for gaps or reject non-equivalent sources."""

    next_between_row_index = 0
    ranges: dict[int, tuple[int, int]] = {}
    for gap in layout_view.gaps:
        if gap.placement is PromptReorderGapPlacement.BETWEEN_ROWS:
            row_indices = range(
                next_between_row_index,
                max(0, len(layout_view.rows) - 1),
            )
        else:
            row_indices = range(
                max(0, len(layout_view.rows) - 1),
                len(layout_view.rows),
            )
        resolved_range: tuple[int, int] | None = None
        for row_index in row_indices:
            row = layout_view.rows[row_index]
            if not row.chip_indices:
                continue
            preceding_chip = chips_by_index.get(row.chip_indices[-1])
            if (
                preceding_chip is None
                or preceding_chip.separator_text_after != gap.separator_text
            ):
                continue
            start = preceding_chip.selection_end
            end = start + len(gap.separator_text)
            if source_text[start:end] != gap.separator_text:
                continue
            resolved_range = (start, end)
            if gap.placement is PromptReorderGapPlacement.BETWEEN_ROWS:
                next_between_row_index = row_index + 1
            break
        if resolved_range is None:
            return None
        ranges[gap.gap_index] = resolved_range
    return ranges


__all__ = ["live_gap_ranges_for_layout"]

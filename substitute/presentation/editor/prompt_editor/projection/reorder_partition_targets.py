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

"""Restrict prompt reorder targets to one regional prompt partition."""

from __future__ import annotations

from dataclasses import replace

from substitute.application.prompt_editor.reorder.views import (
    PromptGapBlankLineDropTarget,
    PromptLineDropTarget,
    PromptReorderLayoutView,
)

from .reorder_placement_geometry import PromptReorderPlacementSnapshot


def partition_drop_placements(
    snapshot: PromptReorderPlacementSnapshot,
    layout_view: PromptReorderLayoutView,
) -> PromptReorderPlacementSnapshot:
    """Return only targets belonging to the partition of the hidden chip."""

    dragged_chip_index = _hidden_chip_index(layout_view)
    if dragged_chip_index is None:
        return snapshot
    partition_index = layout_view.partition_index_by_chip_index[dragged_chip_index]
    allowed_rows = {
        row.row_index
        for row in layout_view.rows
        if row.partition_index == partition_index
    }
    allowed_gaps = {
        gap.gap_index
        for gap in layout_view.gaps
        if gap.partition_index == partition_index
    }
    return replace(
        snapshot,
        placements=tuple(
            placement
            for placement in snapshot.placements
            if (
                isinstance(placement.target, PromptLineDropTarget)
                and placement.target.row_index in allowed_rows
            )
            or (
                isinstance(placement.target, PromptGapBlankLineDropTarget)
                and placement.target.gap_index in allowed_gaps
            )
        ),
    )


def _hidden_chip_index(layout_view: PromptReorderLayoutView) -> int | None:
    """Return the one catalog chip omitted from a base-drag layout."""

    visible_indices = {
        chip_index for row in layout_view.rows for chip_index in row.chip_indices
    }
    hidden_indices = tuple(
        chip_index
        for chip_index in range(len(layout_view.partition_index_by_chip_index))
        if chip_index not in visible_indices
    )
    if len(hidden_indices) != 1:
        return None
    return hidden_indices[0]


__all__ = ["partition_drop_placements"]

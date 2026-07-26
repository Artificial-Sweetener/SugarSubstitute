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

"""Build immutable prompt reorder target geometry from placements."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from PySide6.QtCore import QRectF

from substitute.application.prompt_editor.reorder.views import (
    PromptGapBlankLineDropTarget,
    PromptLineDropTarget,
)

from .reorder_drop_targets import (
    PromptReorderBlankLineDropLane,
    PromptReorderDropLane,
    PromptReorderDropTargetVisual,
    PromptReorderRowDropLane,
)
from .reorder_placement_geometry import (
    PromptReorderPlacementGeometry,
    PromptReorderPlacementSnapshot,
)


@dataclass(frozen=True, slots=True)
class PromptReorderDropGeometry:
    """Publish synchronized placement, visual-target, and lane geometry."""

    placement_snapshot: PromptReorderPlacementSnapshot
    target_visuals: tuple[PromptReorderDropTargetVisual, ...]
    lanes: tuple[PromptReorderDropLane, ...]


def build_reorder_drop_geometry(
    snapshot: PromptReorderPlacementSnapshot,
) -> PromptReorderDropGeometry:
    """Build synchronized geometry for every structural drop destination."""

    target_visuals = tuple(
        PromptReorderDropTargetVisual(placement.target, placement.hit_rect)
        for placement in snapshot.placements
    )
    row_groups: dict[tuple[int, int], list[PromptReorderPlacementGeometry]] = {}
    blank_lanes: list[PromptReorderBlankLineDropLane] = []
    for placement in snapshot.placements:
        if isinstance(placement.target, PromptGapBlankLineDropTarget):
            blank_lanes.append(
                PromptReorderBlankLineDropLane(
                    target=placement.target,
                    hit_rect=placement.hit_rect,
                )
            )
            continue
        if isinstance(placement.target, PromptLineDropTarget):
            row_groups.setdefault(
                (
                    placement.target.row_index,
                    placement.placement_id.visual_line_index,
                ),
                [],
            ).append(placement)

    row_lanes: list[PromptReorderRowDropLane] = []
    for (row_index, visual_row_index), placements in sorted(row_groups.items()):
        placements.sort(
            key=lambda placement: (
                cast(
                    PromptLineDropTarget,
                    placement.target,
                ).insertion_index
            )
        )
        row_lanes.append(
            PromptReorderRowDropLane(
                row_index=row_index,
                visual_row_index=visual_row_index,
                hit_rect=QRectF(placements[0].visual_line_rect),
                slot_visuals=tuple(
                    PromptReorderDropTargetVisual(
                        placement.target,
                        placement.hit_rect,
                    )
                    for placement in placements
                ),
            )
        )

    lanes: list[PromptReorderDropLane] = [*row_lanes, *blank_lanes]
    lanes.sort(key=lambda lane: lane.hit_rect.center().y())
    return PromptReorderDropGeometry(
        placement_snapshot=snapshot,
        target_visuals=target_visuals,
        lanes=tuple(lanes),
    )


__all__ = [
    "PromptReorderDropGeometry",
    "build_reorder_drop_geometry",
]

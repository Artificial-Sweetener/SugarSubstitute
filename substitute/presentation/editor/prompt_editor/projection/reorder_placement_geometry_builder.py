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

"""Build reorder drop placements for one visible row of chip geometry."""

from __future__ import annotations

from PySide6.QtCore import QRectF

from substitute.application.prompt_editor import PromptLineDropTarget

from .reorder_chip_geometry import (
    PromptReorderChipGeometry,
    PromptReorderChipLineGeometry,
)
from .reorder_placement_geometry import (
    PromptReorderPlacementGeometry,
    rect_from_centerline,
    reorder_placement_id_for_target,
)


def build_row_reorder_placements(
    *,
    row_indices: tuple[int, ...],
    line_items: list[
        tuple[int, PromptReorderChipGeometry, PromptReorderChipLineGeometry]
    ],
    row_index: int,
    visual_line_index: int,
    visual_line_rect: QRectF,
    viewport_rect: QRectF,
    ordinal_start: int,
) -> list[PromptReorderPlacementGeometry]:
    """Return projection-owned placements for one visible row of chips."""

    placements: list[PromptReorderPlacementGeometry] = []
    visual_rects = tuple(line.content_rect for _index, _geometry, line in line_items)
    row_top = min((rect.top() for rect in visual_rects), default=visual_line_rect.top())
    row_bottom = max(
        (rect.bottom() for rect in visual_rects),
        default=visual_line_rect.bottom(),
    )
    placement_line_rect = QRectF(
        viewport_rect.left(),
        min(visual_line_rect.top(), row_top),
        viewport_rect.width(),
        max(
            1.0,
            max(visual_line_rect.bottom(), row_bottom)
            - min(visual_line_rect.top(), row_top),
        ),
    ).intersected(viewport_rect)
    if placement_line_rect.isEmpty():
        return placements
    line_top = placement_line_rect.top()
    line_height = max(1.0, placement_line_rect.height())

    def append_placement(
        *,
        insertion_index: int,
        hit_left: float,
        hit_right: float,
        anchor_x: float,
        source_before: int | None,
        source_after: int | None,
        adjacent_chip_indices: tuple[int, ...],
    ) -> None:
        """Append one row-relative insertion target."""

        target = PromptLineDropTarget(
            row_index=row_index,
            insertion_index=insertion_index,
        )
        ordinal = ordinal_start + len(placements)
        placements.append(
            PromptReorderPlacementGeometry(
                placement_id=reorder_placement_id_for_target(
                    target,
                    visual_line_index=visual_line_index,
                    ordinal=ordinal,
                ),
                target=target,
                hit_rect=QRectF(
                    hit_left,
                    line_top,
                    max(8.0, hit_right - hit_left),
                    line_height,
                ).intersected(viewport_rect),
                insertion_anchor_rect=rect_from_centerline(
                    x=anchor_x,
                    y=placement_line_rect.center().y(),
                    height=line_height,
                ),
                visual_line_rect=placement_line_rect,
                expected_landing_rect=None,
                source_before=source_before,
                source_after=source_after,
                adjacent_chip_indices=adjacent_chip_indices,
            )
        )

    first_segment_index, first_geometry, first_line = line_items[0]
    first_rect = QRectF(first_line.content_rect)
    first_logical_index = row_indices.index(first_segment_index)
    append_placement(
        insertion_index=first_logical_index,
        hit_left=viewport_rect.left(),
        hit_right=first_rect.center().x(),
        anchor_x=first_line.leading_anchor.x(),
        source_before=None,
        source_after=first_geometry.rendered_start,
        adjacent_chip_indices=(first_segment_index,),
    )

    for visual_insertion_index, (
        left_segment_index,
        left_geometry,
        left_line,
    ) in enumerate(line_items[:-1], start=1):
        right_segment_index, right_geometry, right_line = line_items[
            visual_insertion_index
        ]
        left_rect = QRectF(left_line.content_rect)
        right_rect = QRectF(right_line.content_rect)
        right_logical_index = row_indices.index(right_segment_index)
        append_placement(
            insertion_index=right_logical_index,
            hit_left=left_rect.center().x(),
            hit_right=right_rect.center().x(),
            anchor_x=right_line.leading_anchor.x(),
            source_before=left_geometry.rendered_end,
            source_after=right_geometry.rendered_start,
            adjacent_chip_indices=(left_segment_index, right_segment_index),
        )

    last_segment_index, last_geometry, last_line = line_items[-1]
    last_rect = QRectF(last_line.content_rect)
    last_logical_index = row_indices.index(last_segment_index)
    append_placement(
        insertion_index=last_logical_index + 1,
        hit_left=last_rect.center().x(),
        hit_right=viewport_rect.right(),
        anchor_x=last_line.trailing_anchor.x(),
        source_before=last_geometry.rendered_end,
        source_after=None,
        adjacent_chip_indices=(last_segment_index,),
    )
    return placements


__all__ = ["build_row_reorder_placements"]

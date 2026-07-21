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

"""Build immutable reorder-chip geometry from visible projection fragments."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF

from .reorder_chip_geometry import (
    PROMPT_REORDER_CHIP_BUBBLE_PADDING_X,
    PROMPT_REORDER_CHIP_BUBBLE_PADDING_Y,
    PROMPT_REORDER_CHIP_HOTSPOT_PADDING_X,
    PROMPT_REORDER_CHIP_HOTSPOT_PADDING_Y,
    PromptReorderChipFragment,
    PromptReorderChipGeometry,
    PromptReorderChipGeometryId,
    PromptReorderChipLineGeometry,
    chrome_path_from_rects,
)


def build_reorder_chip_geometry(
    *,
    chip_index: int,
    visual_revision: int,
    rendered_start: int,
    rendered_end: int,
    fragments: tuple[PromptReorderChipFragment, ...],
    viewport_rect: QRectF,
    line_rects: dict[int, QRectF],
) -> PromptReorderChipGeometry:
    """Build one semantic chip geometry from projection-owned fragments."""

    line_content_rects: dict[int, list[QRectF]] = {}
    for fragment in fragments:
        line_content_rects.setdefault(fragment.visual_line_index, []).append(
            _chip_content_rect_for_fragment(
                fragment.rect,
                viewport_rect=viewport_rect,
            )
        )

    line_geometries: list[PromptReorderChipLineGeometry] = []
    for visual_line_index, content_rects in sorted(line_content_rects.items()):
        content_rect = QRectF(content_rects[0])
        for rect in content_rects[1:]:
            content_rect = content_rect.united(rect)
        line_rect = line_rects.get(
            visual_line_index,
            QRectF(
                viewport_rect.left(),
                content_rect.top(),
                viewport_rect.width(),
                max(1.0, content_rect.height()),
            ),
        )
        line_geometries.append(
            PromptReorderChipLineGeometry(
                visual_line_index=visual_line_index,
                line_rect=QRectF(line_rect),
                content_rect=content_rect,
                leading_anchor=QPointF(content_rect.left(), content_rect.center().y()),
                trailing_anchor=QPointF(
                    content_rect.right(),
                    content_rect.center().y(),
                ),
            )
        )

    outline_bounds = QRectF(line_geometries[0].content_rect)
    for line_geometry in line_geometries[1:]:
        outline_bounds = outline_bounds.united(line_geometry.content_rect)
    hotspot_rect = outline_bounds.adjusted(
        -PROMPT_REORDER_CHIP_HOTSPOT_PADDING_X,
        -PROMPT_REORDER_CHIP_HOTSPOT_PADDING_Y,
        PROMPT_REORDER_CHIP_HOTSPOT_PADDING_X,
        PROMPT_REORDER_CHIP_HOTSPOT_PADDING_Y,
    ).toAlignedRect()
    return PromptReorderChipGeometry(
        geometry_id=PromptReorderChipGeometryId(
            chip_index=chip_index,
            visual_revision=visual_revision,
        ),
        chip_index=chip_index,
        source_start=rendered_start,
        source_end=rendered_end,
        rendered_start=rendered_start,
        rendered_end=rendered_end,
        visual_lines=tuple(line_geometries),
        hotspot_rect=hotspot_rect,
        chrome_path=chrome_path_from_rects(
            tuple(line.content_rect for line in line_geometries)
        ),
        outline_bounds=outline_bounds,
        slot_before=QPointF(
            line_geometries[0].content_rect.left(),
            line_geometries[0].content_rect.center().y(),
        ),
        slot_after=QPointF(
            line_geometries[-1].content_rect.right(),
            line_geometries[-1].content_rect.center().y(),
        ),
        marker_height=max(line.content_rect.height() for line in line_geometries),
    )


def _chip_content_rect_for_fragment(
    fragment: QRectF,
    *,
    viewport_rect: QRectF,
) -> QRectF:
    """Inflate one projection fragment into semantic chip chrome content."""

    return QRectF(
        QPointF(
            max(
                viewport_rect.left(),
                fragment.left() - PROMPT_REORDER_CHIP_BUBBLE_PADDING_X,
            ),
            max(
                viewport_rect.top(),
                fragment.top() - PROMPT_REORDER_CHIP_BUBBLE_PADDING_Y,
            ),
        ),
        QPointF(
            min(
                viewport_rect.right(),
                fragment.right() + PROMPT_REORDER_CHIP_BUBBLE_PADDING_X,
            ),
            min(
                viewport_rect.bottom(),
                fragment.bottom() + PROMPT_REORDER_CHIP_BUBBLE_PADDING_Y,
            ),
        ),
    )


__all__ = ["build_reorder_chip_geometry"]

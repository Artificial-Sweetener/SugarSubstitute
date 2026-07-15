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

"""Describe projection-owned geometry for semantic prompt reorder chips."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRect, QRectF
from PySide6.QtGui import QPainterPath

from .observability import reorder_drag_rect_context

PROMPT_REORDER_CHIP_BUBBLE_PADDING_X = 4.0
PROMPT_REORDER_CHIP_BUBBLE_PADDING_Y = 2.0
PROMPT_REORDER_CHIP_BUBBLE_RADIUS = 9.0
PROMPT_REORDER_CHIP_HOTSPOT_PADDING_X = 5
PROMPT_REORDER_CHIP_HOTSPOT_PADDING_Y = 3


@dataclass(frozen=True, slots=True)
class PromptReorderChipGeometryId:
    """Identify one semantic reorder chip geometry in diagnostics."""

    chip_index: int
    visual_revision: int


@dataclass(frozen=True, slots=True)
class PromptReorderChipLineGeometry:
    """Describe one visual-line contribution to a semantic reorder chip."""

    visual_line_index: int
    line_rect: QRectF
    content_rect: QRectF
    leading_anchor: QPointF
    trailing_anchor: QPointF


@dataclass(frozen=True, slots=True)
class PromptReorderChipGeometry:
    """Describe one semantic reorder chip as projection-owned geometry."""

    geometry_id: PromptReorderChipGeometryId
    chip_index: int
    source_start: int
    source_end: int
    rendered_start: int
    rendered_end: int
    visual_lines: tuple[PromptReorderChipLineGeometry, ...]
    hotspot_rect: QRect
    chrome_path: QPainterPath
    outline_bounds: QRectF
    slot_before: QPointF
    slot_after: QPointF
    marker_height: float


@dataclass(frozen=True, slots=True)
class PromptReorderChipGeometrySnapshot:
    """Describe all semantic reorder chip geometries for one projection layout."""

    geometries_by_chip_index: dict[int, PromptReorderChipGeometry]
    ordered_chip_indices: tuple[int, ...]
    visual_line_count: int
    layout_width: float
    content_height: float
    scroll_offset: float


def chip_geometry_id_context(
    geometry_id: PromptReorderChipGeometryId | None,
    *,
    prefix: str = "chip_geometry_id",
) -> dict[str, object]:
    """Return prompt-content-safe logging context for one chip geometry id."""

    if geometry_id is None:
        return {
            f"{prefix}_chip_index": None,
            f"{prefix}_visual_revision": None,
        }
    return {
        f"{prefix}_chip_index": geometry_id.chip_index,
        f"{prefix}_visual_revision": geometry_id.visual_revision,
    }


def chip_line_geometry_context(
    line_geometry: PromptReorderChipLineGeometry,
    *,
    prefix: str = "chip_line",
) -> dict[str, object]:
    """Return prompt-content-safe logging context for one chip visual line."""

    return {
        f"{prefix}_visual_line_index": line_geometry.visual_line_index,
        **reorder_drag_rect_context(line_geometry.line_rect, prefix=f"{prefix}_line"),
        **reorder_drag_rect_context(
            line_geometry.content_rect,
            prefix=f"{prefix}_content",
        ),
        f"{prefix}_leading_anchor_x": f"{line_geometry.leading_anchor.x():.2f}",
        f"{prefix}_leading_anchor_y": f"{line_geometry.leading_anchor.y():.2f}",
        f"{prefix}_trailing_anchor_x": f"{line_geometry.trailing_anchor.x():.2f}",
        f"{prefix}_trailing_anchor_y": f"{line_geometry.trailing_anchor.y():.2f}",
    }


def chip_geometry_context(
    geometry: PromptReorderChipGeometry | None,
    *,
    prefix: str = "chip_geometry",
) -> dict[str, object]:
    """Return prompt-content-safe logging context for one chip geometry."""

    if geometry is None:
        return {
            f"{prefix}_chip_index": None,
            f"{prefix}_line_count": 0,
            f"{prefix}_has_path": False,
        }
    return {
        **chip_geometry_id_context(geometry.geometry_id, prefix=prefix),
        f"{prefix}_source_start": geometry.source_start,
        f"{prefix}_source_end": geometry.source_end,
        f"{prefix}_source_length": geometry.source_end - geometry.source_start,
        f"{prefix}_rendered_start": geometry.rendered_start,
        f"{prefix}_rendered_end": geometry.rendered_end,
        f"{prefix}_rendered_length": geometry.rendered_end - geometry.rendered_start,
        f"{prefix}_line_count": len(geometry.visual_lines),
        f"{prefix}_has_path": not geometry.chrome_path.isEmpty(),
        f"{prefix}_marker_height": f"{geometry.marker_height:.2f}",
        **reorder_drag_rect_context(
            QRectF(geometry.hotspot_rect),
            prefix=f"{prefix}_hotspot",
        ),
        **reorder_drag_rect_context(
            geometry.outline_bounds,
            prefix=f"{prefix}_outline",
        ),
    }


def chip_geometry_snapshot_context(
    snapshot: PromptReorderChipGeometrySnapshot | None,
    *,
    prefix: str = "chip_geometry_snapshot",
) -> dict[str, object]:
    """Return prompt-content-safe logging context for one chip geometry snapshot."""

    if snapshot is None:
        return {
            f"{prefix}_geometry_count": 0,
            f"{prefix}_ordered_count": 0,
            f"{prefix}_visual_line_count": 0,
        }
    return {
        f"{prefix}_geometry_count": len(snapshot.geometries_by_chip_index),
        f"{prefix}_ordered_count": len(snapshot.ordered_chip_indices),
        f"{prefix}_visual_line_count": snapshot.visual_line_count,
        f"{prefix}_layout_width": f"{snapshot.layout_width:.2f}",
        f"{prefix}_content_height": f"{snapshot.content_height:.2f}",
        f"{prefix}_scroll_offset": f"{snapshot.scroll_offset:.2f}",
    }


def chrome_path_from_rects(rects: tuple[QRectF, ...]) -> QPainterPath:
    """Return one semantic chrome path from chip visual-line rects."""

    path = QPainterPath()
    for rect in rects:
        line_path = QPainterPath()
        line_path.addRoundedRect(
            rect,
            PROMPT_REORDER_CHIP_BUBBLE_RADIUS,
            PROMPT_REORDER_CHIP_BUBBLE_RADIUS,
        )
        path = path.united(line_path)
    return path.simplified()


__all__ = [
    "PromptReorderChipGeometry",
    "PromptReorderChipGeometryId",
    "PromptReorderChipGeometrySnapshot",
    "PromptReorderChipLineGeometry",
    "PROMPT_REORDER_CHIP_BUBBLE_PADDING_X",
    "PROMPT_REORDER_CHIP_BUBBLE_PADDING_Y",
    "PROMPT_REORDER_CHIP_BUBBLE_RADIUS",
    "PROMPT_REORDER_CHIP_HOTSPOT_PADDING_X",
    "PROMPT_REORDER_CHIP_HOTSPOT_PADDING_Y",
    "chip_geometry_context",
    "chip_geometry_id_context",
    "chip_geometry_snapshot_context",
    "chip_line_geometry_context",
    "chrome_path_from_rects",
]

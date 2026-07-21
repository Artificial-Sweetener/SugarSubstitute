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

"""Reuse viewport-local reorder chip geometry across pure scroll changes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRect, QRectF

from substitute.application.prompt_editor import PromptReorderLayoutView

from .reorder_chip_geometry import (
    PromptReorderChipGeometry,
    PromptReorderChipGeometrySnapshot,
    PromptReorderChipLineGeometry,
)

if TYPE_CHECKING:
    from .layout_engine import PromptProjectionLayout


@dataclass(frozen=True, slots=True)
class PromptReorderScrollGeometryReuse:
    """Carry translated interior geometries and indices requiring exact rebuild."""

    geometries_by_chip_index: dict[int, PromptReorderChipGeometry]
    rebuild_chip_indices: frozenset[int]


@dataclass(frozen=True, slots=True)
class PromptReorderScrollGeometryBuildResult:
    """Carry a current snapshot plus translated and rebuilt chip counts."""

    snapshot: PromptReorderChipGeometrySnapshot
    translated_chip_count: int
    rebuilt_chip_count: int


def build_reorder_geometry_after_scroll(
    projection_layout: PromptProjectionLayout,
    *,
    layout_view: PromptReorderLayoutView,
    chip_rendered_ranges_by_index: dict[int, tuple[int, int]],
    chip_owned_ranges_by_index: dict[int, tuple[tuple[int, int], ...]],
    previous_snapshot: PromptReorderChipGeometrySnapshot,
    previous_viewport_rect: QRectF,
    current_viewport_rect: QRectF,
    current_scroll_offset: float,
) -> PromptReorderScrollGeometryBuildResult:
    """Build current geometry by translating interior chips and rebuilding edges."""

    visible_indices = visible_reorder_chip_indices(
        chip_rendered_ranges_by_index,
        visible_source_bounds=projection_layout.visible_source_bounds(
            viewport_rect=current_viewport_rect,
            scroll_offset=current_scroll_offset,
        ),
    )
    reuse = reuse_reorder_geometry_after_scroll(
        previous_snapshot,
        previous_viewport_rect=previous_viewport_rect,
        current_viewport_rect=current_viewport_rect,
        current_scroll_offset=current_scroll_offset,
        visible_chip_indices=visible_indices,
    )
    rebuilt_snapshot = projection_layout.reorder_chip_geometry_snapshot(
        layout_view=layout_view,
        chip_rendered_ranges_by_index=chip_rendered_ranges_by_index,
        chip_owned_ranges_by_index=chip_owned_ranges_by_index,
        viewport_rect=current_viewport_rect,
        scroll_offset=current_scroll_offset,
        included_chip_indices=reuse.rebuild_chip_indices,
    )
    snapshot = merged_reorder_chip_geometry_snapshot(
        translated_geometries=reuse.geometries_by_chip_index,
        rebuilt_snapshot=rebuilt_snapshot,
        scroll_offset=current_scroll_offset,
    )
    return PromptReorderScrollGeometryBuildResult(
        snapshot=snapshot,
        translated_chip_count=len(reuse.geometries_by_chip_index),
        rebuilt_chip_count=len(rebuilt_snapshot.geometries_by_chip_index),
    )


def visible_reorder_chip_indices(
    chip_rendered_ranges_by_index: dict[int, tuple[int, int]],
    *,
    visible_source_bounds: tuple[int, int] | None,
) -> frozenset[int]:
    """Return chips whose rendered source ranges can intersect the viewport."""

    if visible_source_bounds is None:
        return frozenset()
    visible_start, visible_end = visible_source_bounds
    return frozenset(
        chip_index
        for chip_index, (chip_start, chip_end) in chip_rendered_ranges_by_index.items()
        if chip_start < visible_end and visible_start < chip_end
    )


def reuse_reorder_geometry_after_scroll(
    previous_snapshot: PromptReorderChipGeometrySnapshot,
    *,
    previous_viewport_rect: QRectF,
    current_viewport_rect: QRectF,
    current_scroll_offset: float,
    visible_chip_indices: frozenset[int],
) -> PromptReorderScrollGeometryReuse:
    """Translate fully captured interior chips and rebuild viewport-edge chips."""

    scroll_delta = previous_snapshot.scroll_offset - current_scroll_offset
    reused: dict[int, PromptReorderChipGeometry] = {}
    rebuild = set(visible_chip_indices)
    for chip_index in visible_chip_indices:
        geometry = previous_snapshot.geometries_by_chip_index.get(chip_index)
        if geometry is None or not _is_fully_captured(
            geometry,
            viewport_rect=previous_viewport_rect,
        ):
            continue
        translated = _translated_geometry(geometry, vertical_delta=scroll_delta)
        if not QRectF(translated.hotspot_rect).intersects(current_viewport_rect):
            continue
        reused[chip_index] = translated
        rebuild.discard(chip_index)
    return PromptReorderScrollGeometryReuse(
        geometries_by_chip_index=reused,
        rebuild_chip_indices=frozenset(rebuild),
    )


def merged_reorder_chip_geometry_snapshot(
    *,
    translated_geometries: dict[int, PromptReorderChipGeometry],
    rebuilt_snapshot: PromptReorderChipGeometrySnapshot,
    scroll_offset: float,
) -> PromptReorderChipGeometrySnapshot:
    """Merge translated and rebuilt chip geometry into one current snapshot."""

    geometries = dict(translated_geometries)
    geometries.update(rebuilt_snapshot.geometries_by_chip_index)
    return PromptReorderChipGeometrySnapshot(
        geometries_by_chip_index=geometries,
        ordered_chip_indices=rebuilt_snapshot.ordered_chip_indices,
        visual_line_count=rebuilt_snapshot.visual_line_count,
        layout_width=rebuilt_snapshot.layout_width,
        content_height=rebuilt_snapshot.content_height,
        scroll_offset=scroll_offset,
    )


def _is_fully_captured(
    geometry: PromptReorderChipGeometry,
    *,
    viewport_rect: QRectF,
) -> bool:
    """Return whether no chip content rect was clipped by the old viewport."""

    return all(
        line.content_rect.top() > viewport_rect.top()
        and line.content_rect.bottom() < viewport_rect.bottom()
        for line in geometry.visual_lines
    )


def _translated_geometry(
    geometry: PromptReorderChipGeometry,
    *,
    vertical_delta: float,
) -> PromptReorderChipGeometry:
    """Return one immutable geometry translated by a pure scroll delta."""

    return PromptReorderChipGeometry(
        geometry_id=geometry.geometry_id,
        chip_index=geometry.chip_index,
        source_start=geometry.source_start,
        source_end=geometry.source_end,
        rendered_start=geometry.rendered_start,
        rendered_end=geometry.rendered_end,
        visual_lines=tuple(
            PromptReorderChipLineGeometry(
                visual_line_index=line.visual_line_index,
                line_rect=line.line_rect.translated(0.0, vertical_delta),
                content_rect=line.content_rect.translated(0.0, vertical_delta),
                leading_anchor=line.leading_anchor + QPointF(0.0, vertical_delta),
                trailing_anchor=line.trailing_anchor + QPointF(0.0, vertical_delta),
            )
            for line in geometry.visual_lines
        ),
        hotspot_rect=QRect(geometry.hotspot_rect).translated(
            0,
            int(round(vertical_delta)),
        ),
        chrome_path=geometry.chrome_path.translated(0.0, vertical_delta),
        outline_bounds=geometry.outline_bounds.translated(0.0, vertical_delta),
        slot_before=geometry.slot_before + QPointF(0.0, vertical_delta),
        slot_after=geometry.slot_after + QPointF(0.0, vertical_delta),
        marker_height=geometry.marker_height,
    )


__all__ = [
    "PromptReorderScrollGeometryBuildResult",
    "PromptReorderScrollGeometryReuse",
    "build_reorder_geometry_after_scroll",
    "merged_reorder_chip_geometry_snapshot",
    "reuse_reorder_geometry_after_scroll",
    "visible_reorder_chip_indices",
]

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

"""Contract tests for semantic prompt reorder chip geometry values."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, QRectF

from substitute.presentation.editor.prompt_editor.projection.reorder_chip_geometry import (
    PromptReorderChipGeometry,
    PromptReorderChipGeometryId,
    PromptReorderChipGeometrySnapshot,
    PromptReorderChipLineGeometry,
    chip_geometry_context,
    chip_geometry_snapshot_context,
    chrome_path_from_rects,
)


def test_reorder_chip_geometry_context_is_prompt_content_safe() -> None:
    """Chip geometry diagnostics should expose ranges and rects, not prompt text."""

    line = PromptReorderChipLineGeometry(
        visual_line_index=2,
        line_rect=QRectF(0.0, 20.0, 200.0, 18.0),
        content_rect=QRectF(10.0, 22.0, 90.0, 16.0),
        leading_anchor=QPointF(10.0, 30.0),
        trailing_anchor=QPointF(100.0, 30.0),
    )
    geometry = PromptReorderChipGeometry(
        geometry_id=PromptReorderChipGeometryId(chip_index=4, visual_revision=7),
        chip_index=4,
        source_start=12,
        source_end=38,
        rendered_start=12,
        rendered_end=38,
        visual_lines=(line,),
        hotspot_rect=QRect(5, 18, 102, 24),
        chrome_path=chrome_path_from_rects((line.content_rect,)),
        outline_bounds=QRectF(line.content_rect),
        slot_before=QPointF(10.0, 30.0),
        slot_after=QPointF(100.0, 30.0),
        marker_height=16.0,
    )

    context = chip_geometry_context(geometry)

    assert context["chip_geometry_chip_index"] == 4
    assert context["chip_geometry_rendered_length"] == 26
    assert context["chip_geometry_has_path"] is True
    assert all("black underbust" not in str(value) for value in context.values())


def test_reorder_chip_geometry_snapshot_preserves_one_key_per_chip_index() -> None:
    """A snapshot should be keyed by semantic chip identity, not visual fragments."""

    line = PromptReorderChipLineGeometry(
        visual_line_index=0,
        line_rect=QRectF(0.0, 0.0, 100.0, 20.0),
        content_rect=QRectF(4.0, 2.0, 80.0, 18.0),
        leading_anchor=QPointF(4.0, 11.0),
        trailing_anchor=QPointF(84.0, 11.0),
    )
    geometry = PromptReorderChipGeometry(
        geometry_id=PromptReorderChipGeometryId(chip_index=1, visual_revision=0),
        chip_index=1,
        source_start=0,
        source_end=10,
        rendered_start=0,
        rendered_end=10,
        visual_lines=(line,),
        hotspot_rect=QRect(0, 0, 90, 24),
        chrome_path=chrome_path_from_rects((line.content_rect,)),
        outline_bounds=QRectF(line.content_rect),
        slot_before=QPointF(4.0, 11.0),
        slot_after=QPointF(84.0, 11.0),
        marker_height=18.0,
    )
    snapshot = PromptReorderChipGeometrySnapshot(
        geometries_by_chip_index={1: geometry},
        ordered_chip_indices=(1,),
        visual_line_count=1,
        layout_width=100.0,
        content_height=20.0,
        scroll_offset=0.0,
    )

    context = chip_geometry_snapshot_context(snapshot)

    assert tuple(snapshot.geometries_by_chip_index) == (1,)
    assert context["chip_geometry_snapshot_geometry_count"] == 1
    assert context["chip_geometry_snapshot_ordered_count"] == 1

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

"""Cover safe reorder chip geometry translation across viewport scrolls."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, QRectF
from PySide6.QtGui import QPainterPath

from substitute.presentation.editor.prompt_editor.projection.reorder_chip_geometry import (
    PromptReorderChipGeometry,
    PromptReorderChipGeometryId,
    PromptReorderChipGeometrySnapshot,
    PromptReorderChipLineGeometry,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_scroll_geometry import (
    reuse_reorder_geometry_after_scroll,
)


def test_scroll_geometry_reuse_translates_interior_and_rebuilds_edge_chips() -> None:
    """Only fully captured interior chip geometry should translate across scroll."""

    previous = PromptReorderChipGeometrySnapshot(
        geometries_by_chip_index={
            0: _geometry(0, top=20.0),
            1: _geometry(1, top=0.0),
        },
        ordered_chip_indices=(0, 1, 2),
        visual_line_count=3,
        layout_width=200.0,
        content_height=300.0,
        scroll_offset=0.0,
    )

    result = reuse_reorder_geometry_after_scroll(
        previous,
        previous_viewport_rect=QRectF(0.0, 0.0, 200.0, 100.0),
        current_viewport_rect=QRectF(0.0, 0.0, 200.0, 100.0),
        current_scroll_offset=8.0,
        visible_chip_indices=frozenset({0, 1, 2}),
    )

    translated = result.geometries_by_chip_index[0]
    assert translated.outline_bounds.top() == 12.0
    assert translated.slot_before.y() == 21.0
    assert result.rebuild_chip_indices == frozenset({1, 2})


def _geometry(chip_index: int, *, top: float) -> PromptReorderChipGeometry:
    """Return one deterministic single-line chip geometry."""

    content = QRectF(4.0, top, 40.0, 18.0)
    path = QPainterPath()
    path.addRect(content)
    return PromptReorderChipGeometry(
        geometry_id=PromptReorderChipGeometryId(
            chip_index=chip_index,
            visual_revision=chip_index,
        ),
        chip_index=chip_index,
        source_start=chip_index * 6,
        source_end=chip_index * 6 + 5,
        rendered_start=chip_index * 6,
        rendered_end=chip_index * 6 + 5,
        visual_lines=(
            PromptReorderChipLineGeometry(
                visual_line_index=chip_index,
                line_rect=QRectF(0.0, top, 200.0, 18.0),
                content_rect=content,
                leading_anchor=QPointF(4.0, top + 9.0),
                trailing_anchor=QPointF(44.0, top + 9.0),
            ),
        ),
        hotspot_rect=QRect(4, int(top), 40, 18),
        chrome_path=path,
        outline_bounds=content,
        slot_before=QPointF(4.0, top + 9.0),
        slot_after=QPointF(44.0, top + 9.0),
        marker_height=18.0,
    )

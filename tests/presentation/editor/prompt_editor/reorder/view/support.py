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

"""Provide shared prompt reorder view publications."""

from __future__ import annotations


from PySide6.QtCore import QPointF, QRect, QRectF
from PySide6.QtGui import QColor, QFont, QPixmap
from PySide6.QtWidgets import QApplication

from substitute.presentation.editor.prompt_editor.overlays.chip_visuals import (
    PromptChipVisual,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_visual_style import (
    PromptReorderVisualStyle,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_raster_cache import (
    ReorderRasterEntry,
    ReorderRasterKey,
    ReorderRasterStyleKey,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_visual_snapshot import (
    PromptReorderProjectionPaintSnapshot,
    PromptReorderProjectionSnapshotKey,
    PromptReorderTextPaintFragment,
    reorder_projection_paint_content_key,
)


def _style() -> PromptReorderVisualStyle:
    """Return a reorder visual style with state-distinct colors."""

    return PromptReorderVisualStyle(
        rest_fill=QColor(10, 10, 10, 10),
        rest_border=QColor(20, 20, 20, 20),
        hover_fill=QColor(30, 30, 30, 30),
        hover_border=QColor(40, 40, 40, 40),
        active_fill=QColor(50, 50, 50, 50),
        active_border=QColor(60, 60, 60, 60),
        drag_fill=QColor(70, 70, 70, 70),
        drag_border=QColor(80, 80, 80, 80),
        marker_color=QColor(90, 90, 90, 90),
    )


def _visual(left: float) -> PromptChipVisual:
    """Return one deterministic chip visual for render-state tests."""

    bubble = QRectF(left, 4.0, 30.0, 14.0)
    return PromptChipVisual(
        bubble_rects=(bubble,),
        fragment_union_rect=QRectF(bubble),
        hotspot_rect=QRect(int(left), 0, 40, 22),
        slot_before=QPointF(bubble.left(), bubble.center().y()),
        slot_after=QPointF(bubble.right(), bubble.center().y()),
        marker_height=bubble.height(),
    )


def _projection_snapshot(
    segment_index: int,
    *,
    left: float = 80.0,
    text: str = "alpha",
    preview_generation: int | None = 2,
    geometry_generation: int = 3,
) -> PromptReorderProjectionPaintSnapshot:
    """Return a deterministic projection paint snapshot for render-state tests."""

    fragments = (
        ()
        if not text
        else (
            PromptReorderTextPaintFragment(
                text=text,
                font=QFont(),
                baseline=QPointF(left + 4.0, 16.0),
                text_rect=QRectF(left + 4.0, 4.0, max(1.0, len(text) * 6.0), 14.0),
                color=QColor(10, 20, 30),
            ),
        )
    )
    return PromptReorderProjectionPaintSnapshot(
        key=PromptReorderProjectionSnapshotKey(
            source_revision=1,
            viewport_rect=QRect(0, 0, 300, 120),
            scroll_offset=0,
            font_key="test-font",
            palette_key=1,
            preview_generation=preview_generation,
            geometry_generation=geometry_generation,
            segment_index=segment_index,
            mode="preview",
        ),
        fragments=fragments,
        source_ranges=() if not text else ((0, len(text)),),
        content_key=reorder_projection_paint_content_key(fragments),
    )


def _raster_entry(
    *,
    segment_index: int = 0,
    left: float = 80.0,
) -> ReorderRasterEntry:
    """Return one deterministic raster entry for render-state tests."""

    if QApplication.instance() is None:
        QApplication([])
    logical_rect = QRectF(left, 0.0, 40.0, 22.0)
    return ReorderRasterEntry(
        key=ReorderRasterKey(
            content_key="test",
            device_pixel_ratio=1.0,
            style_key=ReorderRasterStyleKey(
                fill_rgba=1,
                border_rgba=2,
                outline_only=False,
                outline_width=1.0,
                opacity=1.0,
            ),
        ),
        segment_index=segment_index,
        pixmap=QPixmap(46, 28),
        logical_rect=logical_rect,
        raster_rect=QRectF(left - 3.0, -3.0, 46.0, 28.0),
    )

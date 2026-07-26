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

"""Paint prepared prompt reorder state without owning preparation or policy."""

from __future__ import annotations

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QPaintEvent, QPainter, QPainterPath, QRegion
from PySide6.QtWidgets import QWidget

from ..projection.chip_painter import PromptProjectionChipPainter
from ..projection.observability import (
    log_reorder_drag_event,
    log_reorder_drag_timing,
    reorder_drag_started_at,
)
from ..projection.reorder_visual_snapshot import paint_reorder_projection_snapshot
from .chip_painter import PromptChipPainter
from .chip_visuals import PROMPT_CHIP_BUBBLE_RADIUS, PromptChipVisual
from .reorder_render_state import (
    PromptReorderChipPaintState,
    PromptReorderLandingPreviewPaintState,
    PromptReorderMarkerPaintState,
    PromptReorderViewRenderState,
)
from .reorder_visual_cache import translated_snapshot_offset

_REORDER_MARKER_RADIUS = 3.0
_REORDER_PAINT_BUDGET_MS = 8.0


class PromptReorderView(QWidget):
    """Paint prepared reorder chrome while leaving gesture and layout elsewhere."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the passive reorder paint surface."""

        super().__init__(parent)
        self.setObjectName("segmentReorderView")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._render_state = PromptReorderViewRenderState()
        self._paint_region = QRegion()
        self._chip_painter = PromptChipPainter()
        self._projection_chip_painter = PromptProjectionChipPainter()

    @property
    def render_state(self) -> PromptReorderViewRenderState:
        """Return the prepared render state currently painted by the view."""

        return self._render_state

    def set_render_state(self, state: PromptReorderViewRenderState) -> None:
        """Replace the prepared render state and schedule a repaint."""

        previous_region = QRegion(self._paint_region)
        self._render_state = state
        self._paint_region = _paint_region_for_render_state(state)
        exposed_region = previous_region.subtracted(self._paint_region)
        parent = self.parentWidget()
        if parent is not None and not exposed_region.isEmpty():
            parent.update(exposed_region)
        self.update(self._paint_region)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint prepared reorder chips, landing previews, and insertion markers."""

        started_at = reorder_drag_started_at()
        state = self._render_state
        if self._paint_region.isEmpty():
            return
        painter = QPainter(self)
        paint_bounds = event.region().boundingRect()
        try:
            painter.setClipRegion(self._paint_region)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            self._paint_chips(
                painter,
                state.preview_chips if state.preview_active else state.live_chips,
            )
            if state.landing_preview is not None:
                self._paint_landing_preview(painter, state.landing_preview)
            if state.marker is not None:
                self._paint_marker(painter, state.marker)
        finally:
            painter.end()
        paint_elapsed_ms = log_reorder_drag_timing(
            "reorder_view.paint",
            started_at=started_at,
            gesture_id=state.gesture_id,
            event_id=state.event_id,
            preview_active=state.preview_active,
            preview_visual_count=len(state.preview_chips),
            live_visual_count=len(state.live_chips),
            marker_visible=state.marker is not None,
            landing_preview_visible=state.landing_preview is not None,
            dragged_segment_index=state.dragged_segment_index,
            paint_bounds_width=paint_bounds.width(),
            paint_bounds_height=paint_bounds.height(),
        )
        if paint_elapsed_ms >= _REORDER_PAINT_BUDGET_MS:
            log_reorder_drag_event(
                "budget.reorder_view_paint_exceeded",
                gesture_id=state.gesture_id,
                event_id=state.event_id,
                elapsed_ms=f"{paint_elapsed_ms:.3f}",
                threshold_ms=f"{_REORDER_PAINT_BUDGET_MS:.3f}",
            )

    def _paint_chips(
        self,
        painter: QPainter,
        chips: tuple[PromptReorderChipPaintState, ...],
    ) -> None:
        """Paint every prepared reorder chip in order."""

        for chip in chips:
            if chip.raster_entry is not None and chip.visual is not None:
                painter.drawPixmap(
                    chip.raster_entry.top_left_for_rect(
                        QRectF(chip.visual.hotspot_rect)
                    ),
                    chip.raster_entry.pixmap,
                )
                continue
            if chip.visual_snapshot is not None and chip.visual is not None:
                self._chip_painter.paint_chrome(
                    painter=painter,
                    visual=chip.visual,
                    style=chip.style,
                )
                dx, dy = translated_snapshot_offset(
                    painted_rect=QRectF(chip.visual.hotspot_rect),
                    snapshot=chip.visual_snapshot,
                )
                painter.save()
                painter.translate(dx, dy)
                paint_reorder_projection_snapshot(
                    painter,
                    chip.visual_snapshot.projection_snapshot,
                )
                painter.restore()
                continue
            if chip.geometry is not None:
                self._projection_chip_painter.paint_chip_geometry(
                    painter=painter,
                    geometry=chip.geometry,
                    style=chip.style,
                )
            elif chip.visual is not None:
                self._chip_painter.paint_chrome(
                    painter=painter,
                    visual=chip.visual,
                    style=chip.style,
                )

    def _paint_landing_preview(
        self,
        painter: QPainter,
        landing_preview: PromptReorderLandingPreviewPaintState,
    ) -> None:
        """Paint the prepared landing preview or pending fallback shadow."""

        if landing_preview.geometry is not None:
            self._projection_chip_painter.paint_chip_geometry(
                painter=painter,
                geometry=landing_preview.geometry,
                style=landing_preview.style,
            )
        elif landing_preview.visual is not None:
            self._chip_painter.paint_chrome(
                painter=painter,
                visual=landing_preview.visual,
                style=landing_preview.style,
            )

    @staticmethod
    def _paint_marker(
        painter: QPainter,
        marker: PromptReorderMarkerPaintState,
    ) -> None:
        """Paint one prepared insertion marker."""

        painter.setBrush(marker.color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(
            marker.rect,
            _REORDER_MARKER_RADIUS,
            _REORDER_MARKER_RADIUS,
        )


def _paint_region_for_render_state(state: PromptReorderViewRenderState) -> QRegion:
    """Return the widget region owned by the current reorder paint state."""

    region = QRegion()
    chips = state.preview_chips if state.preview_active else state.live_chips
    for chip in chips:
        chip_region = _paint_region_for_chip(chip)
        if not chip_region.isEmpty():
            region = region.united(chip_region)
    if state.landing_preview is not None:
        landing_region = _paint_region_for_landing_preview(state.landing_preview)
        if not landing_region.isEmpty():
            region = region.united(landing_region)
    if state.marker is not None:
        region = region.united(QRegion(_expanded_aligned_rect(state.marker.rect)))
    return region


def _paint_region_for_chip(chip: PromptReorderChipPaintState) -> QRegion:
    """Return the exact overlay region needed to paint one chip."""

    if chip.geometry is not None:
        return _paint_region_for_path(chip.geometry.chrome_path)
    if chip.visual is not None:
        return _paint_region_for_visual(chip.visual)
    return QRegion()


def _paint_region_for_landing_preview(
    landing_preview: PromptReorderLandingPreviewPaintState,
) -> QRegion:
    """Return the overlay region needed to paint a landing preview."""

    if landing_preview.geometry is not None:
        return _paint_region_for_path(landing_preview.geometry.chrome_path)
    if landing_preview.visual is not None:
        return _paint_region_for_visual(landing_preview.visual)
    return QRegion()


def _paint_region_for_visual(visual: PromptChipVisual) -> QRegion:
    """Return the rounded chrome region owned by one prepared chip visual."""

    region = QRegion()
    for bubble_rect in visual.bubble_rects:
        bubble_path = QPainterPath()
        bubble_path.addRoundedRect(
            bubble_rect,
            PROMPT_CHIP_BUBBLE_RADIUS,
            PROMPT_CHIP_BUBBLE_RADIUS,
        )
        region = region.united(_paint_region_for_path(bubble_path))
    return region


def _paint_region_for_path(path: QPainterPath) -> QRegion:
    """Return the integer widget region covered by one prepared chrome path."""

    if path.isEmpty():
        return QRegion()
    return QRegion(path.toFillPolygon().toPolygon())


def _expanded_aligned_rect(rect: QRectF) -> QRect:
    """Return an integer paint rect with antialiasing slack."""

    return rect.toAlignedRect().adjusted(-2, -2, 2, 2)


__all__ = ["PromptReorderView"]

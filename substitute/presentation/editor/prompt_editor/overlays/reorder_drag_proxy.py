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

"""Render the floating reorder drag proxy with shared chip visuals and painting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, cast

from PySide6.QtCore import QPoint, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPaintEvent, QRegion
from PySide6.QtWidgets import QFrame, QWidget

from ..projection.chip_painter import (
    PromptProjectionChipPainter,
    PromptProjectionChipTextPaintPayload,
)
from ..projection.observability import (
    log_reorder_drag_timing,
    reorder_drag_started_at,
)
from .chip_painter import PromptChipPaintStyle, PromptChipPainter
from .chip_visuals import PromptChipVisual


@dataclass(frozen=True, slots=True)
class PromptReorderDragProxyRenderState:
    """Describe prepared chrome and text payload for the floating drag proxy."""

    segment_index: int
    preferred_size: QSize
    chrome_payload: object | None
    text_paint_payload: object | None = None
    fill_color: QColor | None = None
    border_color: QColor | None = None


@dataclass(frozen=True, slots=True)
class PromptReorderDragProxyPlacement:
    """Describe the host-global placement requested for the drag proxy."""

    global_position: QPoint
    visible: bool


class PromptReorderDragProxy(Protocol):
    """Render a prepared floating reorder proxy without owning source state."""

    def set_render_state(self, state: PromptReorderDragProxyRenderState) -> None:
        """Replace the prepared proxy state rendered by the drag proxy."""

    def set_placement(self, placement: PromptReorderDragProxyPlacement) -> None:
        """Move or hide the proxy using prepared global placement data."""

    def preferred_size(self) -> QSize:
        """Return the preferred size for the current prepared proxy state."""

    def hide_proxy(self) -> None:
        """Hide the drag proxy without changing reorder state."""


class PromptReorderDragProxyWidget(QFrame):
    """Render one floating drag proxy using shared chip chrome and geometry rules."""

    def __init__(
        self,
        *,
        object_name: str,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the proxy widget that renders prepared drag state."""

        super().__init__(parent)
        self.setObjectName(object_name)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setProperty("active", False)
        self.setProperty("segmentIndex", -1)
        self._chip_painter = PromptChipPainter()
        self._projection_chip_painter = PromptProjectionChipPainter()
        self._visual: PromptChipVisual | None = None
        self._text_paint_payload: PromptProjectionChipTextPaintPayload | None = None
        self._preferred_size = QSize(1, 1)
        self._paint_style = PromptChipPaintStyle(
            fill_color=QColor(),
            border_color=QColor(),
        )

    def projection_document(self) -> object | None:
        """Return the projection document currently rendered by the drag proxy."""

        if self._text_paint_payload is None:
            return None
        return getattr(self._text_paint_payload, "projection_document", None)

    def text_paint_payload(self) -> object | None:
        """Return the prepared text paint payload currently rendered by the proxy."""

        return self._text_paint_payload

    def preview_text(self) -> str:
        """Return the serialized chip text currently rendered by the drag proxy."""

        if self._text_paint_payload is None:
            return ""
        return self._text_paint_payload.source_text

    def set_render_state(self, state: PromptReorderDragProxyRenderState) -> None:
        """Render prepared proxy chrome and projection text state."""

        total_started_at = reorder_drag_started_at()
        self.setProperty("segmentIndex", state.segment_index)
        self._visual = (
            state.chrome_payload
            if isinstance(state.chrome_payload, PromptChipVisual)
            else None
        )
        self._text_paint_payload = (
            None
            if state.text_paint_payload is None
            else cast(PromptProjectionChipTextPaintPayload, state.text_paint_payload)
        )
        self._preferred_size = QSize(state.preferred_size)
        self._paint_style = PromptChipPaintStyle(
            fill_color=QColor(state.fill_color or QColor()),
            border_color=QColor(state.border_color or QColor()),
        )
        self.adjustSize()
        self._update_bubble_mask()
        log_reorder_drag_timing(
            "drag_proxy_widget.set_render_state",
            started_at=total_started_at,
            segment_index=state.segment_index,
            text_length=len(self.preview_text()),
            width=self.width(),
            height=self.height(),
            bubble_count=0 if self._visual is None else len(self._visual.bubble_rects),
            has_text_payload=self._text_paint_payload is not None,
        )

    def set_placement(self, placement: PromptReorderDragProxyPlacement) -> None:
        """Move or hide the proxy according to prepared placement state."""

        if not placement.visible:
            self.hide()
            return
        parent_widget = self.parentWidget()
        target_position = (
            parent_widget.mapFromGlobal(placement.global_position)
            if parent_widget is not None
            else placement.global_position
        )
        self.move(target_position)
        self.show()

    def preferred_size(self) -> QSize:
        """Return the preferred size for the current prepared render state."""

        return self.sizeHint()

    def hide_proxy(self) -> None:
        """Hide the proxy without changing its prepared render state."""

        self.hide()

    def sizeHint(self) -> QSize:
        """Return the size implied by the current proxy visual."""

        started_at = reorder_drag_started_at()
        size = QSize(
            max(1, self._preferred_size.width()),
            max(1, self._preferred_size.height()),
        )
        log_reorder_drag_timing(
            "drag_proxy_widget.size_hint",
            started_at=started_at,
            width=size.width(),
            height=size.height(),
        )
        return size

    def _update_bubble_mask(self) -> None:
        """Apply a rounded widget mask matching the shared proxy bubble geometry."""

        started_at = reorder_drag_started_at()
        visual = self._visual
        if visual is None or not visual.bubble_rects:
            self.clearMask()
            log_reorder_drag_timing(
                "drag_proxy_widget.update_mask.clear",
                started_at=started_at,
            )
            return
        bubble_mask = QRegion()
        for bubble_rect in visual.bubble_rects:
            bubble_path = QPainterPath()
            bubble_path.addRoundedRect(bubble_rect, 9.0, 9.0)
            bubble_mask = bubble_mask.united(
                QRegion(bubble_path.toFillPolygon().toPolygon())
            )
        self.setMask(bubble_mask)
        log_reorder_drag_timing(
            "drag_proxy_widget.update_mask",
            started_at=started_at,
            bubble_count=len(visual.bubble_rects),
            bounding_width=bubble_mask.boundingRect().width(),
            bounding_height=bubble_mask.boundingRect().height(),
        )

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the shared bubble chrome plus projection-backed proxy text."""

        started_at = reorder_drag_started_at()
        _ = event
        visual = self._visual
        text_paint_payload = self._text_paint_payload
        if text_paint_payload is None or visual is None:
            log_reorder_drag_timing(
                "drag_proxy_widget.paint.skipped",
                started_at=started_at,
                has_text_payload=text_paint_payload is not None,
                has_visual=visual is not None,
            )
            return
        painter = QPainter(self)
        try:
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_SourceOver
            )
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            self._chip_painter.paint_chrome(
                painter=painter,
                visual=visual,
                style=self._paint_style,
            )
            self._projection_chip_painter.paint_projection_text_payload(
                painter=painter,
                payload=text_paint_payload,
                visual=visual,
                clip_rect=QRectF(
                    0.0,
                    0.0,
                    max(1.0, self.width()),
                    max(1.0, self.height()),
                ),
            )
        finally:
            painter.end()
        log_reorder_drag_timing(
            "drag_proxy_widget.paint",
            started_at=started_at,
            text_length=len(text_paint_payload.source_text),
            bubble_count=len(visual.bubble_rects),
            width=self.width(),
            height=self.height(),
        )


__all__ = [
    "PromptReorderDragProxy",
    "PromptReorderDragProxyPlacement",
    "PromptReorderDragProxyRenderState",
    "PromptReorderDragProxyWidget",
]

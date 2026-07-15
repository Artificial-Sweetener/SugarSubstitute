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

"""Own passive fill-plane and resize-handle prompt-editor shell chrome."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPaintEvent, QPainter, QRegion
from PySide6.QtWidgets import QWidget


class PromptFillBand(Protocol):
    """Describe one projection-owned prompt fill band."""

    rect: QRectF
    band_index: int


class PromptFillPlaneSurface(Protocol):
    """Describe the projection data consumed by passive fill-plane painting."""

    def viewport(self) -> QWidget:
        """Return the projection viewport widget."""

    def visible_prompt_fill_band_rects(self) -> tuple[PromptFillBand, ...]:
        """Return visible fill bands in projection viewport coordinates."""

    def prompt_fill_band_color(self) -> QColor:
        """Return the already-prepared fill color for prompt background bands."""


@runtime_checkable
class PromptFillPlaneHost(Protocol):
    """Describe shell geometry needed by passive fill-plane chrome."""

    def _shell_viewport(self) -> QWidget:
        """Return the QFluent shell viewport."""


class PromptResizeHandleHost(Protocol):
    """Describe the public widget API needed by the resize handle."""

    def height(self) -> int:
        """Return the current editor shell height."""

    def setManualScrollHeight(self, height: int | None) -> None:  # noqa: N802
        """Apply a user-requested manual prompt height."""


class PromptResizeHandle(QWidget):
    """Capture manual prompt viewport resize gestures outside the text surface."""

    _HEIGHT = 8

    def __init__(self, editor: PromptResizeHandleHost) -> None:
        """Create a quiet bottom-edge resize handle for scrollable prompts."""

        super().__init__(editor if isinstance(editor, QWidget) else None)
        self._editor = editor
        self._drag_start_global_y: int | None = None
        self._drag_start_height = 0
        self.setObjectName("PromptEditorResizeHandle")
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self.setFixedHeight(self._HEIGHT)
        self.setMouseTracking(True)
        self.setStyleSheet(
            """
            QWidget#PromptEditorResizeHandle {
                background-color: rgba(128, 128, 128, 32);
                border-radius: 2px;
            }
            QWidget#PromptEditorResizeHandle:hover {
                background-color: rgba(128, 128, 128, 58);
            }
            """
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Begin a manual prompt viewport resize drag."""

        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        self._drag_start_global_y = event.globalPosition().toPoint().y()
        self._drag_start_height = self._editor.height()
        self.grabMouse()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Apply the current resize drag delta to the owning prompt editor."""

        if self._drag_start_global_y is None:
            super().mouseMoveEvent(event)
            return
        delta_y = event.globalPosition().toPoint().y() - self._drag_start_global_y
        requested_height = self._drag_start_height + delta_y
        self._editor.setManualScrollHeight(requested_height)
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Finish a manual prompt viewport resize drag."""

        if self._drag_start_global_y is None:
            super().mouseReleaseEvent(event)
            return
        self.releaseMouse()
        self._drag_start_global_y = None
        self._drag_start_height = 0
        event.accept()


class PromptFillPlane(QWidget):
    """Own prompt content fill effects inside the QFluent shell."""

    _FLUENT_BORDER_WIDTH = 1

    def __init__(
        self,
        editor: PromptFillPlaneHost,
        surface: PromptFillPlaneSurface,
        parent: QWidget,
        *,
        shell_padding_only: bool,
    ) -> None:
        """Create a passive fill plane for prompt background effects."""

        super().__init__(parent)
        self._editor = editor
        self._surface = surface
        self._shell_padding_only = shell_padding_only
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def mapped_prompt_fill_band_rects(self) -> tuple[tuple[QRectF, int], ...]:
        """Return prompt fill rows mapped into this layer's coordinates."""

        projection_viewport = self._surface.viewport()
        projection_origin = QPointF(
            self._map_widget_point_to_layer(projection_viewport, QPoint(0, 0))
        )
        mapped = tuple(
            (fill_rect.rect.translated(projection_origin), fill_rect.band_index)
            for fill_rect in self._surface.visible_prompt_fill_band_rects()
        )
        return mapped

    def fill_clip_region(self) -> QRegion:
        """Return the QFluent interior region where prompt fill may paint."""

        border = self._FLUENT_BORDER_WIDTH if self._shell_padding_only else 0
        inner_rect = self.rect().adjusted(border, border, -border, -border)
        if inner_rect.isEmpty():
            return QRegion()
        region = QRegion(inner_rect)
        if self._shell_padding_only:
            region = region.subtracted(QRegion(self._shell_viewport_rect()))
        scrollbar_region = self._visible_scrollbar_region()
        if not scrollbar_region.isEmpty():
            region = region.subtracted(scrollbar_region)
        resize_handle_region = self._visible_resize_handle_region()
        if not resize_handle_region.isEmpty():
            region = region.subtracted(resize_handle_region)
        region.boundingRect()
        return region

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint prompt fill bands without touching prompt text."""

        _ = event
        clip_region = self.fill_clip_region()
        fill_band_rects = self.mapped_prompt_fill_band_rects()
        if clip_region.isEmpty() or not fill_band_rects:
            return
        painter = QPainter(self)
        try:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setClipRegion(clip_region)
            fill_color = self._surface.prompt_fill_band_color()
            border = self._FLUENT_BORDER_WIDTH if self._shell_padding_only else 0
            fill_rect = QRectF(
                self.rect().adjusted(
                    border,
                    border,
                    -border,
                    -border,
                )
            )
            for rect, band_index in fill_band_rects:
                if band_index % 2 == 0:
                    continue
                painter.fillRect(
                    QRectF(
                        fill_rect.left(),
                        rect.top(),
                        fill_rect.width(),
                        rect.height(),
                    ),
                    fill_color,
                )
        finally:
            painter.end()

    def _projection_viewport_rect(self) -> QRect:
        """Return the projection viewport geometry in this layer's coordinates."""

        projection_viewport = self._surface.viewport()
        return QRect(
            self._map_widget_point_to_layer(projection_viewport, QPoint(0, 0)),
            projection_viewport.size(),
        )

    def _shell_viewport_rect(self) -> QRect:
        """Return the QFluent shell viewport geometry in this layer's coordinates."""

        shell_viewport = self._editor._shell_viewport()
        return QRect(
            self._map_widget_point_to_layer(shell_viewport, QPoint(0, 0)),
            shell_viewport.size(),
        )

    def _visible_scrollbar_region(self) -> QRegion:
        """Return the visible QFluent scrollbar geometry in layer coordinates."""

        scroll_delegate = getattr(self._editor, "scrollDelegate", None)
        visible_scrollbar = getattr(scroll_delegate, "vScrollBar", None)
        if (
            not isinstance(visible_scrollbar, QWidget)
            or not visible_scrollbar.isVisible()
        ):
            return QRegion()
        return QRegion(
            QRect(
                self._map_widget_point_to_layer(visible_scrollbar, QPoint(0, 0)),
                visible_scrollbar.size(),
            )
        )

    def _visible_resize_handle_region(self) -> QRegion:
        """Return the visible prompt resize-handle geometry in layer coordinates."""

        resize_handle = getattr(self._editor, "_resize_handle", None)
        if not isinstance(resize_handle, QWidget) or not resize_handle.isVisible():
            return QRegion()
        return QRegion(
            QRect(
                self._map_widget_point_to_layer(resize_handle, QPoint(0, 0)),
                resize_handle.size(),
            )
        )

    def _map_widget_point_to_layer(self, widget: QWidget, point: QPoint) -> QPoint:
        """Map any live widget point into this fill layer's coordinates."""

        return self.mapFromGlobal(widget.mapToGlobal(point))


def update_prompt_fill_backing(
    *,
    rect: QRect,
    surface: PromptFillPlaneSurface,
    shell_viewport: QWidget,
    fill_plane: QWidget,
    shell_padding_fill_plane: QWidget,
) -> None:
    """Repaint shell-owned fill layers under a dirty projection viewport rect."""

    if rect.isEmpty():
        return
    viewport = surface.viewport()
    shell_top_left = shell_viewport.mapFromGlobal(viewport.mapToGlobal(rect.topLeft()))
    shell_rect = QRect(shell_top_left, rect.size())
    shell_viewport.update(shell_rect)
    fill_plane.update(shell_rect)

    shell_padding_top_left = shell_padding_fill_plane.mapFromGlobal(
        viewport.mapToGlobal(rect.topLeft())
    )
    shell_padding_fill_plane.update(QRect(shell_padding_top_left, rect.size()))


__all__ = [
    "PromptFillPlane",
    "PromptFillPlaneHost",
    "PromptFillPlaneSurface",
    "PromptResizeHandle",
    "PromptResizeHandleHost",
    "update_prompt_fill_backing",
]

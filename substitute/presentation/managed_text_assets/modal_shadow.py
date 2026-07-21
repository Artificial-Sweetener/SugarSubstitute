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

"""Paint managed-text modal shadow chrome without filtering editor descendants."""

from __future__ import annotations

import math
from typing import Any, cast

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QLinearGradient,
    QPaintEvent,
    QPainter,
    QPen,
    QPixmap,
    QRegion,
)
from PySide6.QtWidgets import QWidget


class ManagedTextAssetModalShadow(QWidget):
    """Cache modal shadow pixels outside the live editor subtree."""

    _MARGIN = 52
    _OFFSET_Y = 10
    _CORNER_RADIUS = 10.0
    _BLUR_FALLOFF = 13.0
    _EDGE_ALPHA = 25.0
    _INNER_BOTTOM_ALPHA = 39

    def __init__(self, *, modal: QWidget, center_widget: QWidget) -> None:
        """Create a passive sibling shadow and remove the descendant effect."""

        super().__init__(modal)
        self._center_widget = center_widget
        self._pixmap = QPixmap()
        self.setObjectName("ManagedTextAssetModalShadow")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        cast(Any, center_widget).setGraphicsEffect(None)
        center_widget.installEventFilter(self)
        self._sync_to_center_widget()
        self.show()
        self.stackUnder(center_widget)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Follow center-widget geometry and visibility without observing children."""

        if watched is self._center_widget:
            if event.type() in {
                QEvent.Type.Move,
                QEvent.Type.Resize,
                QEvent.Type.Show,
            }:
                self._sync_to_center_widget()
            elif event.type() == QEvent.Type.Hide:
                self.hide()
        return False

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Blit the prepared shadow for the exposed outer ring only."""

        if self._pixmap.isNull():
            return
        painter = QPainter(self)
        try:
            painter.setClipRegion(event.region())
            painter.drawPixmap(QPoint(0, 0), self._pixmap)
        finally:
            painter.end()

    def _sync_to_center_widget(self) -> None:
        """Align the shadow ring to the center card and rebuild size-owned pixels."""

        center_geometry = self._center_widget.geometry()
        shadow_geometry = center_geometry.adjusted(
            -self._MARGIN,
            -self._MARGIN,
            self._MARGIN,
            self._MARGIN,
        )
        geometry_changed = self.geometry() != shadow_geometry
        if geometry_changed:
            self.setGeometry(shadow_geometry)
            self._rebuild_pixmap()
        self.setVisible(self._center_widget.isVisible())
        self.stackUnder(self._center_widget)

    def _rebuild_pixmap(self) -> None:
        """Prepare one size-specific analytical approximation of Fluent shadow."""

        if self.width() <= 0 or self.height() <= 0:
            self._pixmap = QPixmap()
            return
        device_pixel_ratio = max(1.0, float(self.devicePixelRatioF()))
        pixmap = QPixmap(
            max(1, int(math.ceil(self.width() * device_pixel_ratio))),
            max(1, int(math.ceil(self.height() * device_pixel_ratio))),
        )
        pixmap.setDevicePixelRatio(device_pixel_ratio)
        pixmap.fill(Qt.GlobalColor.transparent)
        center_rect = self._center_rect()
        outer_region = QRegion(self.rect()).subtracted(
            QRegion(center_rect.toAlignedRect())
        )
        self.setMask(outer_region)
        painter = QPainter(pixmap)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setClipRegion(outer_region)
            shadow_source = center_rect.translated(0.0, self._OFFSET_Y)
            painter.setPen(Qt.PenStyle.NoPen)
            bottom_gradient = QLinearGradient(
                0.0,
                center_rect.bottom(),
                0.0,
                shadow_source.bottom(),
            )
            bottom_gradient.setColorAt(
                0.0,
                QColor(0, 0, 0, self._INNER_BOTTOM_ALPHA),
            )
            bottom_gradient.setColorAt(
                1.0,
                QColor(0, 0, 0, int(round(self._EDGE_ALPHA))),
            )
            painter.fillRect(
                QRectF(
                    center_rect.left(),
                    center_rect.bottom(),
                    center_rect.width(),
                    self._OFFSET_Y + 1.0,
                ),
                bottom_gradient,
            )
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for distance in range(self._MARGIN, 0, -1):
                alpha = int(
                    round(self._EDGE_ALPHA * math.exp(-distance / self._BLUR_FALLOFF))
                )
                if alpha <= 0:
                    continue
                expanded = shadow_source.adjusted(
                    -distance,
                    -distance,
                    distance,
                    distance,
                )
                painter.setPen(QPen(QColor(0, 0, 0, alpha), 1.25))
                painter.drawRoundedRect(
                    expanded,
                    self._CORNER_RADIUS + distance,
                    self._CORNER_RADIUS + distance,
                )
        finally:
            painter.end()
        self._pixmap = pixmap
        self.update()

    def _center_rect(self) -> QRectF:
        """Return center-card geometry in shadow-widget coordinates."""

        return QRectF(
            QRect(
                self._MARGIN,
                self._MARGIN,
                self._center_widget.width(),
                self._center_widget.height(),
            )
        )


__all__ = ["ManagedTextAssetModalShadow"]

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

"""Own thumbnail presentation and passive input policy for picker previews."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QEnterEvent,
    QMouseEvent,
    QPaintEvent,
    QPainter,
    QPainterPath,
    QPixmap,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QApplication,
    QLabel,
    QStackedLayout,
    QWidget,
)


@runtime_checkable
class _RoundedLiveContent(Protocol):
    """Accept thumbnail chrome geometry at the live renderer boundary."""

    def set_thumbnail_corner_radius(self, radius: int) -> None:
        """Clip live presentation to the supplied logical-pixel radius."""


class _HighlightOverlay(QWidget):
    """Paint picker feedback above either static or live preview pixels."""

    def __init__(self, corner_radius: int, parent: QWidget) -> None:
        """Create a mouse-transparent overlay for one preview surface."""

        super().__init__(parent)
        self._corner_radius = corner_radius
        self._hovered = False
        self._pressed = False
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def set_interaction_state(self, *, hovered: bool, pressed: bool) -> None:
        """Render the current hover and press state."""

        self._hovered = hovered
        self._pressed = pressed
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Draw rounded feedback above preview content when active."""

        super().paintEvent(event)
        if not self._hovered and not self._pressed:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(
            QRectF(self.rect()),
            self._corner_radius,
            self._corner_radius,
        )
        alpha = 82 if self._pressed else 51
        painter.fillPath(path, QColor(100, 100, 100, alpha))


class ThumbnailPreviewSurface(QWidget):
    """Present static or live picker content through one interaction contract."""

    clicked = Signal()

    def __init__(
        self,
        *,
        thumbnail_width: int,
        corner_radius: int,
        shadow_margin: int = 6,
        parent: QWidget | None = None,
    ) -> None:
        """Create one stable clipped surface for every picker presentation mode."""

        super().__init__(parent)
        if thumbnail_width <= 0:
            raise ValueError("thumbnail_width must be positive")
        self._thumbnail_width = thumbnail_width
        self._corner_radius = corner_radius
        self._shadow_margin = shadow_margin
        self._hovered = False
        self._pressed = False
        self._live_content: QWidget | None = None
        self._has_static_content = False

        self._clip_host = QWidget(self)
        self._highlight_overlay = _HighlightOverlay(corner_radius, self)
        self._clip_layout = QStackedLayout(self._clip_host)
        self._clip_layout.setContentsMargins(0, 0, 0, 0)
        self._static_label = QLabel(self._clip_host)
        self._static_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._static_label.setStyleSheet("border: none; background: none;")
        self._clip_layout.addWidget(self._static_label)
        self._clip_layout.setCurrentWidget(self._static_label)

        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMouseTracking(True)
        self.clear_static_content()

    @property
    def static_label(self) -> QLabel:
        """Return the compatibility label used for static thumbnail content."""

        return self._static_label

    def set_static_pixmap(self, pixmap: QPixmap) -> QSize:
        """Display pixels using the exact historical rounded-thumbnail rendering."""

        scaled = pixmap.scaledToWidth(
            self._thumbnail_width,
            Qt.TransformationMode.SmoothTransformation,
        )
        result = self._historical_rounded_pixmap(scaled)
        self._has_static_content = True
        self._static_label.setPixmap(result)
        self._static_label.setFixedSize(result.size())
        self._clip_layout.setCurrentWidget(self._static_label)
        self._set_static_size(result.size())
        self._static_label.show()
        self.show()
        self.update()
        return result.size()

    def clear_static_content(self) -> None:
        """Clear static pixels while retaining a stable default surface width."""

        self._has_static_content = False
        self._static_label.clear()
        self._static_label.setFixedSize(0, 0)
        self._clip_layout.setCurrentWidget(self._static_label)
        self.setFixedSize(0, 0)
        self.hide()

    def set_live_content(self, content: QWidget) -> None:
        """Mount live pixels as passive content under the shared picker chrome."""

        if not isinstance(content, QWidget):
            raise TypeError("content must be a QWidget")
        if not isinstance(content, _RoundedLiveContent):
            raise TypeError("content must accept thumbnail corner geometry")
        self.remove_live_content()
        self._live_content = content
        content.set_thumbnail_corner_radius(self._corner_radius)
        content.setParent(self._clip_host)
        content.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        content.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._clip_layout.addWidget(content)
        self._clip_layout.setCurrentWidget(content)
        content_size = content.sizeHint().expandedTo(QSize(1, 1))
        content.setFixedSize(content_size)
        self._set_live_size(content_size)
        content.show()
        self.show()
        self.update()

    def live_content(self) -> QWidget | None:
        """Return the mounted live content without exposing chrome ownership."""

        return self._live_content

    def remove_live_content(self) -> QWidget | None:
        """Detach and return live content so its lifecycle owner can retire it."""

        content = self._live_content
        if content is None:
            return None
        self._live_content = None
        self._clip_layout.removeWidget(content)
        content.setParent(None)
        self._clip_layout.setCurrentWidget(self._static_label)
        if self._has_static_content:
            self._set_static_size(self._static_label.size())
            self.show()
        else:
            self.setFixedSize(0, 0)
            self.hide()
        self.update()
        return content

    def enterEvent(self, event: QEnterEvent) -> None:
        """Render hover feedback for both static and live content."""

        self._hovered = True
        self._sync_highlight()
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        """Clear hover and press feedback when the pointer leaves."""

        self._hovered = False
        self._pressed = False
        self._sync_highlight()
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Capture left-button press presentation without taking focus."""

        if event.button() is Qt.MouseButton.LeftButton:
            self._pressed = True
            self._sync_highlight()
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Publish one click from the authoritative picker interaction surface."""

        was_pressed = self._pressed
        self._pressed = False
        self._sync_highlight()
        self.update()
        if was_pressed and event.button() is Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Forward wheel input to the nearest scroll-area viewport."""

        parent = self.parentWidget()
        while parent is not None and not isinstance(parent, QAbstractScrollArea):
            parent = parent.parentWidget()
        if not isinstance(parent, QAbstractScrollArea):
            event.ignore()
            return
        viewport = parent.viewport()
        forwarded = QWheelEvent(
            QPointF(viewport.mapFromGlobal(event.globalPosition().toPoint())),
            event.globalPosition(),
            event.pixelDelta(),
            event.angleDelta(),
            event.buttons(),
            event.modifiers(),
            event.phase(),
            event.inverted(),
            event.source(),
            event.pointingDevice(),
        )
        QApplication.sendEvent(viewport, forwarded)
        event.setAccepted(forwarded.isAccepted())

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint shared shadow and hover/press chrome around clipped content."""

        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._live_content is None:
            return
        shadow_rect = QRectF(self._clip_host.geometry())
        path = QPainterPath()
        path.addRoundedRect(shadow_rect, self._corner_radius, self._corner_radius)
        painter.fillPath(path, QColor(0, 0, 0, 60))

    def _set_static_size(self, size: QSize) -> None:
        """Apply the historical already-framed static thumbnail geometry."""

        self._clip_host.setGeometry(0, 0, size.width(), size.height())
        self._highlight_overlay.setGeometry(0, 0, size.width(), size.height())
        self._highlight_overlay.raise_()
        self.setFixedSize(size)

    def _set_live_size(self, size: QSize) -> None:
        """Frame live document pixels inside the historical shadow margins."""

        self._clip_host.setGeometry(
            self._shadow_margin,
            self._shadow_margin,
            size.width(),
            size.height(),
        )
        outer_size = QSize(
            size.width() + self._shadow_margin * 2,
            size.height() + self._shadow_margin * 2,
        )
        self._highlight_overlay.setGeometry(
            0, 0, outer_size.width(), outer_size.height()
        )
        self._highlight_overlay.raise_()
        self.setFixedSize(outer_size)

    def _historical_rounded_pixmap(self, scaled: QPixmap) -> QPixmap:
        """Return the pre-live-preview picker pixmap without aesthetic changes."""

        size = scaled.size()
        result_size = size + QSize(self._shadow_margin * 2, self._shadow_margin * 2)
        result = QPixmap(result_size)
        result.fill(Qt.GlobalColor.transparent)
        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        shadow_rect = QRectF(
            self._shadow_margin,
            self._shadow_margin,
            size.width(),
            size.height(),
        )
        shadow_path = QPainterPath()
        shadow_path.addRoundedRect(
            shadow_rect,
            self._corner_radius,
            self._corner_radius,
        )
        painter.fillPath(shadow_path, QColor(0, 0, 0, 60))
        image_path = QPainterPath()
        image_path.addRoundedRect(
            QRectF(0, 0, size.width(), size.height()),
            self._corner_radius,
            self._corner_radius,
        )
        painter.setClipPath(
            image_path.translated(self._shadow_margin, self._shadow_margin)
        )
        painter.drawPixmap(self._shadow_margin, self._shadow_margin, scaled)
        painter.end()
        return result

    def _sync_highlight(self) -> None:
        """Project surface interaction state into the topmost overlay."""

        self._highlight_overlay.set_interaction_state(
            hovered=self._hovered,
            pressed=self._pressed,
        )


__all__ = ["ThumbnailPreviewSurface"]

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

"""Render and clip the private surfaces mounted by a Settings expander."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import Property, QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QPixmap,
    QResizeEvent,
    QTransform,
)
from PySide6.QtWidgets import QSizePolicy, QWidget
from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]

from sugarsubstitute_shared.presentation.localization import set_localized_tooltip
from substitute.presentation.settings.settings_card import InteractiveSettingsCard
from substitute.presentation.settings.settings_style import (
    SETTINGS_CARD_RADIUS,
    SETTINGS_EXPANDER_CHEVRON_BUTTON_SIZE,
    settings_card_border_color,
    settings_card_fill_color,
)

_CHEVRON_ICON_SIZE = 14


class SettingsExpanderPaintSurface(QWidget):
    """Paint one attached segment of a Settings expander surface."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create a transparent paint surface with detachable corners."""

        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent; border: none;")
        self._content_attached = False

    def set_content_attached(self, attached: bool) -> None:
        """Set whether this segment is visually connected to another segment."""

        self._content_attached = attached
        self.update()

    def set_accordion_content_attached(self, attached: bool) -> None:
        """Apply attachment state from shared accordion motion code."""

        self.set_content_attached(attached)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the Settings expander segment background and border."""

        _ = event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(0, 0, -1, -1)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(settings_card_fill_color(self))
        painter.drawPath(self._paint_path(rect))
        pen = QPen(settings_card_border_color(), 1)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self._stroke_path(rect))

    def _paint_path(self, rect: QRect) -> QPainterPath:
        """Return the rounded fill path for this segment."""

        path = QPainterPath()
        x = float(rect.x())
        y = float(rect.y())
        width = float(rect.width())
        height = float(rect.height())
        radius = min(float(SETTINGS_CARD_RADIUS), width / 2.0, height / 2.0)
        top_left = self._top_left_radius(radius)
        top_right = self._top_right_radius(radius)
        bottom_right = self._bottom_right_radius(radius)
        bottom_left = self._bottom_left_radius(radius)

        path.moveTo(x + top_left, y)
        path.lineTo(x + width - top_right, y)
        if top_right:
            path.quadTo(x + width, y, x + width, y + top_right)
        path.lineTo(x + width, y + height - bottom_right)
        if bottom_right:
            path.quadTo(x + width, y + height, x + width - bottom_right, y + height)
        path.lineTo(x + bottom_left, y + height)
        if bottom_left:
            path.quadTo(x, y + height, x, y + height - bottom_left)
        path.lineTo(x, y + top_left)
        if top_left:
            path.quadTo(x, y, x + top_left, y)
        path.closeSubpath()
        return path

    def _stroke_path(self, rect: QRect) -> QPainterPath:
        """Return the border path for this segment."""

        return self._paint_path(rect)

    def _top_left_radius(self, radius: float) -> float:
        """Return this segment's top-left corner radius."""

        return radius

    def _top_right_radius(self, radius: float) -> float:
        """Return this segment's top-right corner radius."""

        return radius

    def _bottom_right_radius(self, radius: float) -> float:
        """Return this segment's bottom-right corner radius."""

        return radius

    def _bottom_left_radius(self, radius: float) -> float:
        """Return this segment's bottom-left corner radius."""

        return radius


class SettingsExpanderHeaderSurface(SettingsExpanderPaintSurface):
    """Paint the Settings expander header segment."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create a header surface with optional card attachment forwarding."""

        super().__init__(parent)
        self._header_card: InteractiveSettingsCard | None = None

    def set_header_card(self, card: InteractiveSettingsCard) -> None:
        """Bind the child header card that owns hover overlay shape."""

        self._header_card = card

    def set_content_attached(self, attached: bool) -> None:
        """Apply attached state to the header surface and hover overlay."""

        super().set_content_attached(attached)
        if self._header_card is not None:
            self._header_card.set_expander_header_attached(attached)

    def _paint_path(self, rect: QRect) -> QPainterPath:
        """Return the header fill path without an antialiased attached bottom edge."""

        if not self._content_attached:
            return super()._paint_path(rect)
        return super()._paint_path(rect.adjusted(0, 0, 0, 1))

    def _stroke_path(self, rect: QRect) -> QPainterPath:
        """Return the header border path without duplicating the body separator."""

        if not self._content_attached:
            return super()._stroke_path(rect)

        path = QPainterPath()
        x = float(rect.x())
        y = float(rect.y())
        width = float(rect.width())
        height = float(rect.height())
        radius = min(float(SETTINGS_CARD_RADIUS), width / 2.0, height / 2.0)
        top_left = self._top_left_radius(radius)
        top_right = self._top_right_radius(radius)

        path.moveTo(x, y + top_left)
        if top_left:
            path.quadTo(x, y, x + top_left, y)
        path.lineTo(x + width - top_right, y)
        if top_right:
            path.quadTo(x + width, y, x + width, y + top_right)
        path.lineTo(x + width, y + height)
        path.moveTo(x, y + height)
        path.lineTo(x, y + top_left)
        return path

    def _bottom_right_radius(self, radius: float) -> float:
        """Square the bottom-right corner while content is expanded."""

        return 0.0 if self._content_attached else radius

    def _bottom_left_radius(self, radius: float) -> float:
        """Square the bottom-left corner while content is expanded."""

        return 0.0 if self._content_attached else radius


class SettingsExpanderContentSurface(SettingsExpanderPaintSurface):
    """Paint the Settings expander content segment."""

    def _top_left_radius(self, radius: float) -> float:
        """Square the top-left corner while attached to the header."""

        return 0.0 if self._content_attached else radius

    def _top_right_radius(self, radius: float) -> float:
        """Square the top-right corner while attached to the header."""

        return 0.0 if self._content_attached else radius

    def _stroke_path(self, rect: QRect) -> QPainterPath:
        """Return the content border path without repainting the header join."""

        if not self._content_attached:
            return super()._stroke_path(rect)

        path = QPainterPath()
        x = float(rect.x())
        y = float(rect.y())
        width = float(rect.width())
        height = float(rect.height())
        radius = min(float(SETTINGS_CARD_RADIUS), width / 2.0, height / 2.0)
        bottom_right = self._bottom_right_radius(radius)
        bottom_left = self._bottom_left_radius(radius)

        path.moveTo(x + width, y)
        path.lineTo(x + width, y + height - bottom_right)
        if bottom_right:
            path.quadTo(x + width, y + height, x + width - bottom_right, y + height)
        path.lineTo(x + bottom_left, y + height)
        if bottom_left:
            path.quadTo(x, y + height, x, y + height - bottom_left)
        path.lineTo(x, y)
        return path


class SettingsExpanderContentClip(QWidget):
    """Clip and vertically translate the animated Settings expander body."""

    def __init__(
        self,
        parent: QWidget | None,
        content_surface: QWidget,
    ) -> None:
        """Create a clipped host around the moving content surface."""

        super().__init__(parent)
        self._content_offset_y = 0
        self._content_height = 0
        self._content_surface = content_surface
        self._content_surface.setParent(self)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent; border: none;")
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

    def content_offset_y(self) -> int:
        """Return the current vertical reveal offset."""

        return self._content_offset_y

    def set_content_offset_y(self, offset_y: int) -> None:
        """Move the clipped body content to one vertical offset."""

        self._content_offset_y = int(offset_y)
        self._sync_content_geometry()

    def set_content_height(self, content_height: int) -> None:
        """Store the natural expanded body height."""

        self._content_height = max(0, int(content_height))
        self._sync_content_geometry()
        self.updateGeometry()

    def content_height(self) -> int:
        """Return the natural expanded body height."""

        return self._content_height

    def sizeHint(self) -> QSize:
        """Return the clipped viewport's natural expanded size."""

        content_hint = self._content_surface.sizeHint()
        return QSize(content_hint.width(), self._content_height)

    def minimumSizeHint(self) -> QSize:
        """Return a zero-height hint for collapsed layout participation."""

        content_hint = self._content_surface.minimumSizeHint()
        return QSize(content_hint.width(), 0)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Keep the moving content width synchronized with the clip width."""

        super().resizeEvent(event)
        self._sync_content_geometry()

    def _sync_content_geometry(self) -> None:
        """Apply current offset and natural height to the content surface."""

        height = max(self._content_height, self._content_surface.sizeHint().height())
        self._content_surface.setGeometry(
            0,
            self._content_offset_y,
            max(0, self.width()),
            max(0, height),
        )

    contentOffsetY = Property(int, content_offset_y, set_content_offset_y)


class SettingsExpanderChevron(QWidget):
    """Render the 32px chevron affordance used by a Settings expander."""

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the chevron with the collapsed visual state."""

        super().__init__(parent)
        self._rotation = 0.0
        self.setFixedSize(
            SETTINGS_EXPANDER_CHEVRON_BUTTON_SIZE,
            SETTINGS_EXPANDER_CHEVRON_BUTTON_SIZE,
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        set_localized_tooltip(self, "Show all settings")

    def rotation_value(self) -> float:
        """Return the current chevron rotation for tests and callers."""

        return self._rotation

    def set_rotation(self, angle: float) -> None:
        """Apply chevron rotation and repaint."""

        self._rotation = angle
        self.update()

    def _get_rotation(self) -> float:
        """Return the current chevron rotation for Qt animation APIs."""

        return self._rotation

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Toggle the owning expander when the chevron is clicked."""

        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Draw the rotated Fluent arrow centered in the chevron box."""

        _ = event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pixmap = _render_rotated_icon(
            FIF.ARROW_DOWN,
            self._rotation,
            _CHEVRON_ICON_SIZE,
        )
        x = (self.width() - pixmap.width()) // 2
        y = (self.height() - pixmap.height()) // 2
        painter.drawPixmap(x, y, pixmap)

    rotation = Property(float, _get_rotation, set_rotation)


def _render_rotated_icon(icon_enum: FIF, angle: float, size: int) -> QPixmap:
    """Return one rotated pixmap for a Fluent icon."""

    pixmap = icon_enum.icon().pixmap(size, size)
    transform = QTransform().rotate(angle)
    return cast(
        QPixmap,
        pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation),
    )


__all__ = [
    "SettingsExpanderContentClip",
    "SettingsExpanderContentSurface",
    "SettingsExpanderChevron",
    "SettingsExpanderHeaderSurface",
]

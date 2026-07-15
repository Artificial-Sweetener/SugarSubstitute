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

"""Provide cohesive WinUI-style expanders for Settings pages."""

from __future__ import annotations

from collections.abc import Iterable
from typing import cast

from PySide6.QtCore import Property, QRect, Qt, Signal
from PySide6.QtCore import QPropertyAnimation, QSize, QTimer
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
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]

from substitute.presentation.settings.settings_card import (
    InteractiveSettingsCard,
    SettingsCard,
)
from substitute.presentation.motion import (
    ACCORDION_COLLAPSE_DURATION_MS,
    ACCORDION_COLLAPSE_EASING_CURVE,
    ACCORDION_EXPAND_DURATION_MS,
    ACCORDION_EXPAND_EASING_CURVE,
    is_reduced_motion_enabled,
    restart_property_animation,
    stop_animation,
)
from substitute.presentation.settings.settings_style import (
    SETTINGS_CARD_RADIUS,
    SETTINGS_EXPANDER_CHEVRON_BUTTON_SIZE,
    settings_card_border_color,
    settings_card_fill_color,
)

_EXPANDED_CHEVRON_ROTATION = 180.0
_COLLAPSED_CHEVRON_ROTATION = 0.0
_CHEVRON_ICON_SIZE = 14
_DIVIDER_SHOW_PROGRESS = 0.72


class _SettingsExpanderPaintSurface(QWidget):
    """Paint one attached segment of a SettingsExpander surface."""

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
        """Paint the SettingsExpander segment background and border."""

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


class _SettingsExpanderHeaderSurface(_SettingsExpanderPaintSurface):
    """Paint the SettingsExpander header segment."""

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


class _SettingsExpanderContentSurface(_SettingsExpanderPaintSurface):
    """Paint the SettingsExpander content segment."""

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


class _SettingsExpanderContentClip(QWidget):
    """Clip and vertically translate the animated SettingsExpander body."""

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
    """Render the 32px chevron affordance used by a settings expander."""

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the chevron with the collapsed visual state."""

        super().__init__(parent)
        self._rotation = _COLLAPSED_CHEVRON_ROTATION
        self.setFixedSize(
            SETTINGS_EXPANDER_CHEVRON_BUTTON_SIZE,
            SETTINGS_EXPANDER_CHEVRON_BUTTON_SIZE,
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Show all settings")

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


class SettingsExpander(QWidget):
    """Render one attached SettingsExpander row stack."""

    expandedChanged = Signal(bool)

    def __init__(
        self,
        *,
        title: str,
        description: str = "",
        visual_widget: QWidget | None = None,
        trailing_widget: QWidget | None = None,
        reserve_visual_space: bool = True,
        content_available: bool = True,
        expanded: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        """Create a WinUI-like settings expander."""

        super().__init__(parent)
        self.setObjectName("SubstituteSettingsExpander")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent; border: none;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self._expanded = False
        self._expanded_height = 0
        self._animation_target_expanded = False
        self._animation_active = False
        self._content_available = content_available
        self._height_refresh_queued = False
        self.chevron = SettingsExpanderChevron(self)
        self.chevron.clicked.connect(self.toggle)
        self.header_surface = _SettingsExpanderHeaderSurface(self)
        self.header_surface.setObjectName("SubstituteSettingsExpanderHeaderSurface")
        self.header_card = InteractiveSettingsCard(
            title=title,
            description=description,
            visual_widget=visual_widget,
            trailing_widget=self._build_trailing_widget(trailing_widget),
            reserve_visual_space=reserve_visual_space,
            appearance="expander_header",
            parent=self.header_surface,
        )
        self.header_surface.set_header_card(self.header_card)
        self.header_card.activated.connect(self.toggle)
        self._body = _SettingsExpanderContentSurface(self)
        self._body.setObjectName("SubstituteSettingsExpanderContentSurface")
        self._body.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(0)
        self._content_clip = _SettingsExpanderContentClip(self, self._body)
        self._header_separator = _SettingsExpanderSeparator(self)
        self._content_offset_animation = QPropertyAnimation(
            self._content_clip,
            b"contentOffsetY",
            self,
        )
        self._chevron_animation = QPropertyAnimation(self.chevron, b"rotation", self)
        self._divider_timer = QTimer(self)
        self._divider_timer.setSingleShot(True)
        self._divider_timer.timeout.connect(self._show_header_separator_after_expand)
        self._content_offset_animation.finished.connect(self._finish_motion)
        self._build_layout()
        self._expanded = expanded and self._content_available
        self._apply_rest_state()

    def add_widget(self, widget: QWidget) -> None:
        """Append one widget to the expanded content body."""

        if self._body_layout.count() > 0:
            self._body_layout.addWidget(_SettingsExpanderSeparator(self._body))
        self._body_layout.addWidget(widget)
        self._queue_expanded_height_refresh()

    def add_widgets(self, widgets: Iterable[QWidget]) -> None:
        """Append multiple widgets to the expanded content body."""

        for widget in widgets:
            self.add_widget(widget)

    def content_widget(self) -> QWidget:
        """Return the widget that owns expanded content layout."""

        return self._body

    def set_content_available(self, available: bool) -> None:
        """Set whether this expander currently has user-visible body content."""

        if self._content_available == available:
            self._apply_rest_state()
            return
        self._stop_motion()
        self._content_available = available
        if not available:
            self._expanded = False
        self._apply_rest_state()

    def has_content_available(self) -> bool:
        """Return whether this expander currently exposes expandable content."""

        return self._content_available

    def body_spacing(self) -> int:
        """Return expanded body row spacing for tests and callers."""

        return self._body_layout.spacing()

    def separator_count(self) -> int:
        """Return the number of full-width separators in the content body."""

        count = 0
        for index in range(self._body_layout.count()):
            item = self._body_layout.itemAt(index)
            if item is None:
                continue
            if isinstance(item.widget(), _SettingsExpanderSeparator):
                count += 1
        return count

    def header_separator_height(self) -> int:
        """Return the fixed header/body separator height."""

        return self._header_separator.height()

    def header_separator_visible(self) -> bool:
        """Return whether the header/body separator is currently visible."""

        return self._header_separator.isVisible()

    def content_offset_y(self) -> int:
        """Return the current animated body reveal offset."""

        return self._content_clip.content_offset_y()

    def content_clip_visible(self) -> bool:
        """Return whether the clipped body participates visibly."""

        return not self._content_clip.isHidden()

    def expanded_content_height(self) -> int:
        """Return the natural expanded content height currently owned by the clip."""

        return self._content_clip.content_height()

    def is_expanded(self) -> bool:
        """Return whether expanded content is currently visible."""

        return self._expanded

    def set_expanded(self, expanded: bool) -> None:
        """Show or hide expanded content."""

        if expanded and not self._content_available:
            self._apply_rest_state()
            return
        if self._expanded == expanded:
            if not self._animation_active:
                self._apply_rest_state()
            return
        self._expanded = expanded
        self._animate_expanded_state(expanded)
        self.expandedChanged.emit(expanded)

    def toggle(self) -> None:
        """Invert the current expansion state."""

        if not self._content_available:
            return
        self.set_expanded(not self._expanded)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Refresh expanded clipping after width-dependent child layout changes."""

        super().resizeEvent(event)
        self._queue_expanded_height_refresh()

    def _build_layout(self) -> None:
        """Create the attached header/content surface layout."""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        header_layout = QVBoxLayout(self.header_surface)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)
        header_layout.addWidget(self.header_card)
        layout.addWidget(self.header_surface)
        layout.addWidget(self._header_separator)
        layout.addWidget(self._content_clip)

    def _build_trailing_widget(self, trailing_widget: QWidget | None) -> QWidget:
        """Create the header trailing area with optional content and chevron."""

        container = QWidget(self)
        container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        container.setStyleSheet("background-color: transparent; border: none;")
        container.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        if trailing_widget is not None:
            trailing_widget.setParent(container)
            layout.addWidget(trailing_widget)
        layout.addWidget(self.chevron)
        return container

    def _animate_expanded_state(self, expanded: bool) -> None:
        """Animate the body and chevron toward one expanded state."""

        self._divider_timer.stop()
        self._expanded_height = self._resolve_expanded_height()
        self._animation_target_expanded = expanded
        self._animation_active = True
        self._prepare_visible_motion()
        self._sync_surface_attachment(True)
        self._header_separator.setVisible(False)
        if expanded and self._content_clip.content_offset_y() == 0:
            self._content_clip.set_content_offset_y(-self._expanded_height)

        target_offset = 0 if expanded else -self._expanded_height
        target_rotation = (
            _EXPANDED_CHEVRON_ROTATION if expanded else _COLLAPSED_CHEVRON_ROTATION
        )
        duration_ms = (
            ACCORDION_EXPAND_DURATION_MS if expanded else ACCORDION_COLLAPSE_DURATION_MS
        )
        easing_curve = (
            ACCORDION_EXPAND_EASING_CURVE
            if expanded
            else ACCORDION_COLLAPSE_EASING_CURVE
        )

        resolved_duration = restart_property_animation(
            self._content_offset_animation,
            start_value=self._content_clip.content_offset_y(),
            end_value=target_offset,
            duration_ms=duration_ms,
            easing_curve=easing_curve,
        )
        restart_property_animation(
            self._chevron_animation,
            start_value=self.chevron.rotation_value(),
            end_value=target_rotation,
            duration_ms=duration_ms,
            easing_curve=easing_curve,
        )

        if expanded:
            if resolved_duration == 0 or is_reduced_motion_enabled():
                self._header_separator.setVisible(True)
            else:
                divider_delay = max(1, int(resolved_duration * _DIVIDER_SHOW_PROGRESS))
                self._divider_timer.start(divider_delay)
        if resolved_duration == 0:
            self._finish_motion()

    def _apply_rest_state(self) -> None:
        """Apply the current state without animated transition."""

        self._stop_motion()
        self._expanded_height = self._resolve_expanded_height()
        body_visible = self._expanded and self._content_available
        offset = 0 if body_visible else -self._expanded_height
        self._content_clip.set_content_height(self._expanded_height)
        self._content_clip.set_content_offset_y(offset)
        self._content_clip.setMaximumHeight(
            self._expanded_height if body_visible else 0
        )
        self._content_clip.setVisible(body_visible)
        self._body.setVisible(body_visible)
        self._header_separator.setVisible(body_visible)
        self.chevron.setVisible(self._content_available)
        self.chevron.set_rotation(
            _EXPANDED_CHEVRON_ROTATION if body_visible else _COLLAPSED_CHEVRON_ROTATION
        )
        self._sync_surface_attachment(body_visible)
        self.updateGeometry()

    def _prepare_visible_motion(self) -> None:
        """Make the clipped body participate visibly during accordion motion."""

        self._content_clip.set_content_height(self._expanded_height)
        self._content_clip.setMaximumHeight(self._expanded_height)
        self._content_clip.setVisible(True)
        self._body.setVisible(True)
        self.chevron.setVisible(self._content_available)
        self._content_clip.updateGeometry()

    def _finish_motion(self) -> None:
        """Settle the body and chevron after an accordion transition."""

        if not self._animation_active:
            return
        self._animation_active = False
        expanded = self._animation_target_expanded and self._content_available
        self._content_clip.set_content_height(self._expanded_height)
        self._content_clip.set_content_offset_y(
            0 if expanded else -self._expanded_height
        )
        self._content_clip.setMaximumHeight(self._expanded_height if expanded else 0)
        self._content_clip.setVisible(expanded)
        self._body.setVisible(expanded)
        self._sync_surface_attachment(expanded)
        self.chevron.set_rotation(
            _EXPANDED_CHEVRON_ROTATION if expanded else _COLLAPSED_CHEVRON_ROTATION
        )
        self._header_separator.setVisible(expanded)
        self.updateGeometry()
        self._queue_expanded_height_refresh()

    def _show_header_separator_after_expand(self) -> None:
        """Reveal the header/body separator near the end of expansion."""

        if self._animation_target_expanded and self._expanded:
            self._header_separator.setVisible(True)

    def _queue_expanded_height_refresh(self) -> None:
        """Refresh expanded height after pending child resize events settle."""

        if not self._expanded or not self._content_available or self._animation_active:
            return
        if self._height_refresh_queued:
            return
        self._height_refresh_queued = True
        QTimer.singleShot(0, self._refresh_expanded_height)

    def _refresh_expanded_height(self) -> None:
        """Update visible clip height to match the current body layout."""

        self._height_refresh_queued = False
        if not self._expanded or not self._content_available or self._animation_active:
            return
        expanded_height = self._resolve_expanded_height()
        if expanded_height == self._expanded_height:
            return
        self._expanded_height = expanded_height
        self._content_clip.set_content_height(expanded_height)
        self._content_clip.set_content_offset_y(0)
        self._content_clip.setMaximumHeight(expanded_height)
        self._content_clip.setVisible(True)
        self._body.setVisible(True)
        self._sync_surface_attachment(True)
        self.updateGeometry()

    def _resolve_expanded_height(self) -> int:
        """Return the natural height of the expanded body surface."""

        self._body_layout.activate()
        return max(
            0,
            self._body_layout.sizeHint().height(),
            self._body.sizeHint().height(),
            self._body.minimumSizeHint().height(),
        )

    def _sync_surface_attachment(self, attached: bool) -> None:
        """Apply attached-corner state to header and body surfaces."""

        self.header_surface.set_content_attached(attached)
        self._body.set_content_attached(attached)

    def _stop_motion(self) -> None:
        """Stop all in-flight accordion motion."""

        self._divider_timer.stop()
        stop_animation(self._content_offset_animation)
        stop_animation(self._chevron_animation)
        self._animation_active = False


class _SettingsExpanderSeparator(QWidget):
    """Render one full-width separator inside an expanded SettingsExpander."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create a fixed-height separator row."""

        super().__init__(parent)
        self.setFixedHeight(1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Draw a full-width separator line."""

        _ = event
        painter = QPainter(self)
        painter.fillRect(self.rect(), settings_card_border_color())


class SettingsExpanderRow(SettingsCard):
    """Render one attached item row inside a SettingsExpander."""

    def __init__(
        self,
        *,
        title: str,
        description: str = "",
        trailing_widget: QWidget | None = None,
        clickable: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        """Create an attached expander item row."""

        super().__init__(
            title=title,
            description=description,
            trailing_widget=trailing_widget,
            reserve_visual_space=False,
            appearance="clickable_expander_item" if clickable else "expander_item",
            parent=parent,
        )


def _render_rotated_icon(icon_enum: FIF, angle: float, size: int) -> QPixmap:
    """Return one rotated pixmap for a Fluent icon."""

    pixmap = icon_enum.icon().pixmap(size, size)
    transform = QTransform().rotate(angle)
    return cast(
        QPixmap,
        pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation),
    )


def expander_body_geometry(expander: SettingsExpander) -> QRect:
    """Return content body geometry for focused widget tests."""

    return QRect(expander.content_widget().geometry())


__all__ = [
    "SettingsExpander",
    "SettingsExpanderChevron",
    "SettingsExpanderRow",
    "expander_body_geometry",
]

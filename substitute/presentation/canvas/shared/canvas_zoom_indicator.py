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

"""Present transient, cursor-relative zoom feedback over QPane canvases."""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose
from typing import TYPE_CHECKING, cast
from uuid import UUID

from PySide6.QtCore import (
    QEvent,
    QObject,
    QPointF,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
)
from PySide6.QtGui import QFont, QFontMetricsF, QMouseEvent, QPainter, QPen, QWheelEvent

from substitute.presentation.canvas.shared.canvas_zoom_indicator_layout import (
    CanvasZoomBadge,
    position_zoom_badges,
)

from substitute.presentation.motion import (
    EXIT_EASING_CURVE,
    resolve_motion_duration,
)
from substitute.presentation.shell.chrome_style import (
    floating_surface_border_color,
    floating_surface_color,
    floating_surface_text_color,
)

if TYPE_CHECKING:
    from qpane import (
        OverlayState,
        QPane,
    )

CANVAS_ZOOM_INDICATOR_OVERLAY_NAME = "substitute-canvas-zoom-indicator"
_GESTURE_TAIL_MS = 250
_VISIBLE_HOLD_MS = 700
_FADE_DURATION_MS = 180
_BADGE_HORIZONTAL_PADDING = 10.0
_BADGE_HEIGHT = 28.0
_BADGE_RADIUS = 8.0
_ZOOM_EPSILON = 1e-6
_ANISOTROPIC_TOLERANCE = 0.01


@dataclass(frozen=True, slots=True)
class CanvasZoomScale:
    """Describe the physical display scale of one image layer."""

    horizontal: float
    vertical: float

    def label(self) -> str:
        """Return a concise percentage label without hiding anisotropic scaling."""

        horizontal = _format_zoom_percentage(self.horizontal)
        if isclose(
            self.horizontal,
            self.vertical,
            rel_tol=_ANISOTROPIC_TOLERANCE,
            abs_tol=_ZOOM_EPSILON,
        ):
            return horizontal
        return f"{horizontal} × {_format_zoom_percentage(self.vertical)}"


class CanvasZoomIndicator(QObject):
    """Own transient zoom gesture state and QPane overlay presentation."""

    def __init__(self, pane: QPane) -> None:
        """Register zoom observation and render-overlay painting."""

        super().__init__(pane)
        self._pane = pane
        self._last_zoom = float(pane.currentZoom())
        self._gesture_armed = False
        self._gesture_position: QPointF | None = None
        self._opacity = 0.0
        self._closed = False
        self._image_sizes: dict[UUID, QSize] = {}
        self._mouse_tracking_was_enabled = pane.hasMouseTracking()

        self._gesture_tail = QTimer(self)
        self._gesture_tail.setSingleShot(True)
        self._gesture_tail.setInterval(_GESTURE_TAIL_MS)
        self._gesture_tail.timeout.connect(self._disarm_zoom_gesture)

        self._hold_timer = QTimer(self)
        self._hold_timer.setSingleShot(True)
        self._hold_timer.setInterval(_VISIBLE_HOLD_MS)
        self._hold_timer.timeout.connect(self._start_fade)

        self._fade = QVariantAnimation(self)
        self._fade.setEasingCurve(EXIT_EASING_CURVE)
        self._fade.valueChanged.connect(self._set_animated_opacity)

        self._refresh_image_sizes()
        pane.zoomChanged.connect(self._on_zoom_changed)
        pane.catalogChanged.connect(self._on_catalog_changed)
        pane.setMouseTracking(True)
        pane.installEventFilter(self)
        pane.registerOverlay(CANVAS_ZOOM_INDICATOR_OVERLAY_NAME, self.draw)

    @property
    def opacity(self) -> float:
        """Return current overlay opacity for presentation diagnostics and tests."""

        return self._opacity

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Track the live cursor and capture zoom gestures without consuming input."""

        if watched is not self._pane:
            return False
        if event.type() == QEvent.Type.MouseMove and self._opacity > 0.0:
            position = _pointing_event_position(event)
            if position is not None:
                self._track_visible_cursor(position)
        elif event.type() in {
            QEvent.Type.Wheel,
            QEvent.Type.MouseButtonDblClick,
        }:
            position = _pointing_event_position(event)
            if position is not None:
                self._gesture_position = position
                self._gesture_armed = True
                self._gesture_tail.start()
        return False

    def _track_visible_cursor(self, position: QPointF) -> None:
        """Repaint visible feedback when the live cursor position changes."""

        if position == self._gesture_position:
            return
        self._gesture_position = position
        self._pane.update()

    def draw(self, painter: QPainter, state: OverlayState) -> None:
        """Paint current zoom feedback from QPane's public render snapshot."""

        if self._opacity <= 0.0:
            return
        badges = self._badges(state)
        if not badges:
            return

        painter.save()
        try:
            painter.setOpacity(painter.opacity() * self._opacity)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            font = QFont(self._pane.font())
            font.setWeight(QFont.Weight.DemiBold)
            painter.setFont(font)
            painter.setBrush(floating_surface_color())
            painter.setPen(QPen(floating_surface_border_color(), 1.0))
            for badge in badges:
                painter.drawRoundedRect(badge.bounds, _BADGE_RADIUS, _BADGE_RADIUS)
            painter.setPen(floating_surface_text_color())
            for badge in badges:
                painter.drawText(
                    badge.bounds,
                    Qt.AlignmentFlag.AlignCenter,
                    badge.text,
                )
        finally:
            painter.restore()

    def close(self) -> None:
        """Disconnect and unregister the overlay during explicit host teardown."""

        if self._closed:
            return
        self._closed = True
        self._gesture_tail.stop()
        self._hold_timer.stop()
        self._fade.stop()
        self._pane.removeEventFilter(self)
        self._pane.setMouseTracking(self._mouse_tracking_was_enabled)
        self._pane.zoomChanged.disconnect(self._on_zoom_changed)
        self._pane.catalogChanged.disconnect(self._on_catalog_changed)
        self._pane.unregisterOverlay(CANVAS_ZOOM_INDICATOR_OVERLAY_NAME)

    def _on_zoom_changed(self, zoom: float) -> None:
        """Show feedback only for meaningful user-initiated zoom changes."""

        next_zoom = float(zoom)
        changed = not isclose(
            self._last_zoom,
            next_zoom,
            rel_tol=_ZOOM_EPSILON,
            abs_tol=_ZOOM_EPSILON,
        )
        self._last_zoom = next_zoom
        if not changed or not self._gesture_armed:
            return
        self._fade.stop()
        self._opacity = 1.0
        self._hold_timer.start()
        self._pane.update()

    def _on_catalog_changed(self, _event: object) -> None:
        """Refresh original image dimensions after public catalog mutations."""

        self._refresh_image_sizes()

    def _refresh_image_sizes(self) -> None:
        """Cache original catalog dimensions outside the overlay paint path."""

        snapshot = self._pane.getCatalogSnapshot()
        self._image_sizes = {
            image_id: QSize(entry.image.size())
            for image_id, entry in snapshot.catalog.items()
            if not entry.image.isNull()
        }

    def _disarm_zoom_gesture(self) -> None:
        """Stop attributing subsequent programmatic viewport changes to the user."""

        self._gesture_armed = False

    def _start_fade(self) -> None:
        """Fade the indicator or hide immediately under reduced-motion policy."""

        duration = resolve_motion_duration(_FADE_DURATION_MS)
        if duration == 0:
            self._set_opacity(0.0)
            return
        self._fade.stop()
        self._fade.setStartValue(self._opacity)
        self._fade.setEndValue(0.0)
        self._fade.setDuration(duration)
        self._fade.start()

    def _set_animated_opacity(self, value: object) -> None:
        """Apply one animation sample and repaint the pane."""

        self._set_opacity(float(cast(float, value)))

    def _set_opacity(self, opacity: float) -> None:
        """Store a bounded opacity and request an overlay repaint."""

        self._opacity = min(1.0, max(0.0, opacity))
        self._pane.update()

    def _badges(self, state: OverlayState) -> tuple[CanvasZoomBadge, ...]:
        """Build normal or comparison badge geometry for one rendered frame."""

        position = self._gesture_position
        if position is None:
            return ()
        font = QFont(self._pane.font())
        font.setWeight(QFont.Weight.DemiBold)
        metrics = QFontMetricsF(font)
        divider = self._pane.comparisonDividerState()
        compare_scales = self._compare_scales(state)
        if not divider.enabled or compare_scales is None:
            text = _format_zoom_percentage(float(state.zoom))
            return position_zoom_badges(
                state.qpane_rect,
                position,
                None,
                CanvasZoomBadge(text, _badge_for_text(text, metrics)),
            )

        base_scale, comparison_scale = compare_scales
        base_text = base_scale.label()
        comparison_text = comparison_scale.label()
        return position_zoom_badges(
            state.qpane_rect,
            position,
            divider,
            CanvasZoomBadge(base_text, _badge_for_text(base_text, metrics)),
            CanvasZoomBadge(
                comparison_text,
                _badge_for_text(comparison_text, metrics),
            ),
        )

    def _compare_scales(
        self,
        state: OverlayState,
    ) -> tuple[CanvasZoomScale, CanvasZoomScale] | None:
        """Derive both compare-image scales from public shared render bounds."""

        comparison = self._pane.comparisonState()
        base_id = self._pane.currentImageID()
        comparison_id = comparison.source_id
        if not comparison.enabled or base_id is None or comparison_id is None:
            return None
        base_size = self._image_sizes.get(base_id)
        comparison_size = self._image_sizes.get(comparison_id)
        if (
            base_size is None
            or comparison_size is None
            or base_size.width() <= 0
            or base_size.height() <= 0
            or comparison_size.width() <= 0
            or comparison_size.height() <= 0
        ):
            return None
        source_bounds = QRectF(
            0.0,
            0.0,
            float(state.source_image.width()),
            float(state.source_image.height()),
        )
        panel_bounds = state.transform.mapRect(source_bounds)
        dpr = max(1.0, float(self._pane.devicePixelRatioF()))
        physical_width = panel_bounds.width() * dpr
        physical_height = panel_bounds.height() * dpr
        return (
            CanvasZoomScale(
                horizontal=physical_width / base_size.width(),
                vertical=physical_height / base_size.height(),
            ),
            CanvasZoomScale(
                horizontal=physical_width / comparison_size.width(),
                vertical=physical_height / comparison_size.height(),
            ),
        )


def _pointing_event_position(event: QEvent) -> QPointF | None:
    """Return the local position carried by a supported zoom gesture event."""

    if isinstance(event, (QWheelEvent, QMouseEvent)):
        return QPointF(event.position())
    return None


def _badge_for_text(text: str, metrics: QFontMetricsF) -> QRectF:
    """Return origin-relative badge bounds sized for one text label."""

    text_bounds = metrics.tightBoundingRect(text)
    return QRectF(
        0.0,
        0.0,
        text_bounds.width() + 2.0 * _BADGE_HORIZONTAL_PADDING,
        _BADGE_HEIGHT,
    )


def _format_zoom_percentage(zoom: float) -> str:
    """Format a positive zoom factor as a compact percentage."""

    percentage = max(0.0, zoom * 100.0)
    if percentage >= 10.0:
        return f"{percentage:.0f}%"
    return f"{percentage:.1f}".rstrip("0").rstrip(".") + "%"


__all__ = [
    "CANVAS_ZOOM_INDICATOR_OVERLAY_NAME",
    "CanvasZoomIndicator",
    "CanvasZoomScale",
]

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

"""Present transient cursor-relative zoom feedback on CuteCanvas targets."""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose
from typing import cast

from PySide6.QtCore import QEvent, QObject, QPointF, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QFont, QFontMetricsF, QMouseEvent, QPainter, QPen, QWheelEvent
from cutecanvas import CanvasOverlayDrawFn, CanvasOverlayState, CuteCanvas

from substitute.presentation.canvas.shared.canvas_zoom_indicator_layout import (
    CanvasZoomBadge,
    position_zoom_badges,
    zoom_badge_for_text,
)
from substitute.presentation.motion import EXIT_EASING_CURVE, resolve_motion_duration
from substitute.presentation.shell.chrome_style import (
    floating_surface_border_color,
    floating_surface_color,
    floating_surface_text_color,
)

CANVAS_ZOOM_INDICATOR_OVERLAY_NAME = "substitute-canvas-zoom-indicator"
_GESTURE_TAIL_MS = 250
_VISIBLE_HOLD_MS = 700
_FADE_DURATION_MS = 180
_BADGE_RADIUS = 8.0
_ZOOM_EPSILON = 1e-6
_ANISOTROPIC_TOLERANCE = 0.01


@dataclass(frozen=True, slots=True)
class CanvasZoomScale:
    """Describe the physical display scale of one rendered image."""

    horizontal: float
    vertical: float

    def label(self) -> str:
        """Return a compact percentage label preserving anisotropic scale."""

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
    """Own cursor-relative zoom feedback for one CuteCanvas detail target."""

    def __init__(self, canvas: CuteCanvas) -> None:
        """Observe one public CuteCanvas target without assuming a presentation role."""

        super().__init__(canvas)
        self._canvas = canvas
        self._last_zoom = canvas.currentZoom()
        self._gesture_armed = False
        self._gesture_position: QPointF | None = None
        self._opacity = 0.0
        self._closed = False
        self._mouse_tracking_was_enabled = canvas.hasMouseTracking()
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
        canvas.zoomChanged.connect(self._on_zoom_changed)
        canvas.setMouseTracking(True)
        canvas.installEventFilter(self)
        canvas.registerCanvasOverlay(
            CANVAS_ZOOM_INDICATOR_OVERLAY_NAME,
            cast(CanvasOverlayDrawFn, self.draw),
        )

    @property
    def opacity(self) -> float:
        """Return current feedback opacity for deterministic diagnostics."""

        return self._opacity

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Track cursor-relative wheel and double-click zoom gestures."""

        if watched is not self._canvas:
            return False
        if event.type() is QEvent.Type.MouseMove and self._opacity > 0.0:
            position = _pointing_event_position(event)
            if position is not None:
                self._track_visible_cursor(position)
        elif event.type() in {QEvent.Type.Wheel, QEvent.Type.MouseButtonDblClick}:
            position = _pointing_event_position(event)
            if position is not None:
                self._gesture_position = position
                self._gesture_armed = True
                self._gesture_tail.start()
        return False

    def draw(self, painter: QPainter, state: CanvasOverlayState) -> None:
        """Paint the current detail-view percentage from the public render snapshot."""

        if self._opacity <= 0.0:
            return
        badges = self._badges(state)
        if not badges:
            return
        painter.save()
        try:
            painter.setOpacity(painter.opacity() * self._opacity)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            font = QFont(self._canvas.font())
            font.setWeight(QFont.Weight.DemiBold)
            painter.setFont(font)
            painter.setBrush(floating_surface_color())
            painter.setPen(QPen(floating_surface_border_color(), 1.0))
            for badge in badges:
                painter.drawRoundedRect(badge.bounds, _BADGE_RADIUS, _BADGE_RADIUS)
            painter.setPen(floating_surface_text_color())
            for badge in badges:
                painter.drawText(badge.bounds, Qt.AlignmentFlag.AlignCenter, badge.text)
        finally:
            painter.restore()

    def close(self) -> None:
        """Disconnect and remove the owned overlay during canvas teardown."""

        if self._closed:
            return
        self._closed = True
        self._gesture_tail.stop()
        self._hold_timer.stop()
        self._fade.stop()
        self._canvas.removeEventFilter(self)
        self._canvas.setMouseTracking(self._mouse_tracking_was_enabled)
        try:
            self._canvas.zoomChanged.disconnect(self._on_zoom_changed)
        except (RuntimeError, TypeError):
            pass
        self._canvas.unregisterCanvasOverlay(CANVAS_ZOOM_INDICATOR_OVERLAY_NAME)

    def _badges(self, state: CanvasOverlayState) -> tuple[CanvasZoomBadge, ...]:
        """Build the one detail-view badge at the active cursor position."""

        position = self._gesture_position
        if position is None:
            return ()
        font = QFont(self._canvas.font())
        font.setWeight(QFont.Weight.DemiBold)
        text = CanvasZoomScale(
            state.display_scale.horizontal,
            state.display_scale.vertical,
        ).label()
        return position_zoom_badges(
            state.viewport,
            position,
            None,
            zoom_badge_for_text(text, QFontMetricsF(font)),
        )

    def _on_zoom_changed(self, zoom: float) -> None:
        """Make feedback visible only for a pointer-originated zoom change."""

        changed = not isclose(
            self._last_zoom,
            float(zoom),
            rel_tol=_ZOOM_EPSILON,
            abs_tol=_ZOOM_EPSILON,
        )
        self._last_zoom = float(zoom)
        if not changed or not self._gesture_armed:
            return
        self._fade.stop()
        self._opacity = 1.0
        self._hold_timer.start()
        self._canvas.update()

    def _track_visible_cursor(self, position: QPointF) -> None:
        """Repaint active feedback when its gesture cursor moves."""

        if position != self._gesture_position:
            self._gesture_position = position
            self._canvas.update()

    def _disarm_zoom_gesture(self) -> None:
        """Stop attributing later programmatic zoom to the pointer gesture."""

        self._gesture_armed = False

    def _start_fade(self) -> None:
        """Fade feedback according to the current application motion policy."""

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
        """Apply one opacity animation sample."""

        self._set_opacity(float(cast(float, value)))

    def _set_opacity(self, opacity: float) -> None:
        """Store bounded opacity and repaint the public canvas overlay."""

        self._opacity = min(1.0, max(0.0, opacity))
        self._canvas.update()


def _pointing_event_position(event: QEvent) -> QPointF | None:
    """Extract a local pointer position from supported zoom gesture events."""

    return (
        QPointF(event.position())
        if isinstance(event, (QWheelEvent, QMouseEvent))
        else None
    )


def _format_zoom_percentage(zoom: float) -> str:
    """Format one nonnegative zoom factor as a compact percentage."""

    percentage = max(0.0, zoom * 100.0)
    return (
        f"{percentage:.0f}%"
        if percentage >= 10.0
        else f"{percentage:.1f}".rstrip("0").rstrip(".") + "%"
    )


__all__ = [
    "CANVAS_ZOOM_INDICATOR_OVERLAY_NAME",
    "CanvasZoomIndicator",
    "CanvasZoomScale",
]

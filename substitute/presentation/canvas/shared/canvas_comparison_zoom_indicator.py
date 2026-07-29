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

"""Present transient two-source zoom feedback on CuteCanvas comparisons."""

from __future__ import annotations

from math import isclose
from typing import cast

from PySide6.QtCore import QObject, QPointF, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QFont, QFontMetricsF, QPainter, QPen
from cutecanvas import (
    CanvasComparisonOverlayState,
    CanvasComparisonZoomGesture,
    CanvasWorkspace,
)

from substitute.presentation.canvas.shared.canvas_zoom_indicator import CanvasZoomScale
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

CANVAS_COMPARISON_ZOOM_INDICATOR_OVERLAY_NAME = (
    "substitute-canvas-comparison-zoom-indicator"
)
_VISIBLE_HOLD_MS = 700
_FADE_DURATION_MS = 180
_BADGE_RADIUS = 8.0
_ZOOM_EPSILON = 1e-6


class CanvasComparisonZoomIndicator(QObject):
    """Own comparison zoom feedback through the CuteCanvas workspace contract."""

    def __init__(self, workspace: CanvasWorkspace) -> None:
        """Register a renderer-free comparison overlay and interaction observers."""

        super().__init__(workspace)
        self._workspace = workspace
        self._gesture_position: QPointF | None = None
        self._last_zoom: float | None = None
        self._opacity = 0.0
        self._closed = False
        self._hold_timer = QTimer(self)
        self._hold_timer.setSingleShot(True)
        self._hold_timer.setInterval(_VISIBLE_HOLD_MS)
        self._hold_timer.timeout.connect(self._start_fade)
        self._fade = QVariantAnimation(self)
        self._fade.setEasingCurve(EXIT_EASING_CURVE)
        self._fade.valueChanged.connect(self._set_animated_opacity)
        workspace.comparisonZoomGesture.connect(self._show_for_zoom_gesture)
        workspace.comparisonPointerMoved.connect(self._track_visible_pointer)
        workspace.registerComparisonOverlay(
            CANVAS_COMPARISON_ZOOM_INDICATOR_OVERLAY_NAME,
            self.draw,
        )

    @property
    def opacity(self) -> float:
        """Return current feedback opacity for deterministic diagnostics."""

        return self._opacity

    def draw(self, painter: QPainter, state: CanvasComparisonOverlayState) -> None:
        """Paint one percentage label in each visible reveal region."""

        if self._opacity <= 0.0 or self._gesture_position is None:
            return
        badges = self._badges(state)
        if not badges:
            return
        painter.save()
        try:
            painter.setOpacity(painter.opacity() * self._opacity)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            font = QFont(self._workspace.font())
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
        """Disconnect the workspace and remove the comparison overlay exactly once."""

        if self._closed:
            return
        self._closed = True
        self._hold_timer.stop()
        self._fade.stop()
        try:
            self._workspace.unregisterComparisonOverlay(
                CANVAS_COMPARISON_ZOOM_INDICATOR_OVERLAY_NAME
            )
        except RuntimeError:
            pass

    def _show_for_zoom_gesture(self, gesture: CanvasComparisonZoomGesture) -> None:
        """Show feedback after CuteCanvas confirms a pointer-originated zoom."""

        changed = self._last_zoom is None or not isclose(
            self._last_zoom,
            gesture.zoom,
            rel_tol=_ZOOM_EPSILON,
            abs_tol=_ZOOM_EPSILON,
        )
        self._last_zoom = gesture.zoom
        if not changed:
            return
        self._gesture_position = QPointF(gesture.position)
        self._fade.stop()
        self._opacity = 1.0
        self._hold_timer.start()
        self._workspace.refreshComparisonOverlays()

    def _track_visible_pointer(self, position: QPointF) -> None:
        """Follow the pointer while comparison feedback remains visible."""

        if self._opacity <= 0.0 or position == self._gesture_position:
            return
        self._gesture_position = QPointF(position)
        self._workspace.refreshComparisonOverlays()

    def _badges(
        self,
        state: CanvasComparisonOverlayState,
    ) -> tuple[CanvasZoomBadge, ...]:
        """Build source-local labels from CuteCanvas's physical display scales."""

        position = self._gesture_position
        if position is None:
            return ()
        font = QFont(self._workspace.font())
        font.setWeight(QFont.Weight.DemiBold)
        metrics = QFontMetricsF(font)
        primary_text = CanvasZoomScale(
            state.primary_scale.horizontal,
            state.primary_scale.vertical,
        ).label()
        secondary_text = CanvasZoomScale(
            state.secondary_scale.horizontal,
            state.secondary_scale.vertical,
        ).label()
        return position_zoom_badges(
            state.viewport,
            position,
            state.divider,
            zoom_badge_for_text(primary_text, metrics),
            zoom_badge_for_text(secondary_text, metrics),
        )

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
        """Store bounded opacity and request the native comparison overlay repaint."""

        self._opacity = min(1.0, max(0.0, opacity))
        self._workspace.refreshComparisonOverlays()


__all__ = [
    "CANVAS_COMPARISON_ZOOM_INDICATOR_OVERLAY_NAME",
    "CanvasComparisonZoomIndicator",
]

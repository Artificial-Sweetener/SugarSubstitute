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

"""Own pointer-driven pan and cursor-centered zoom for video detail."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from PySide6.QtCore import QEvent, QObject, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QWidget

from substitute.presentation.canvas.output.video_playback_controller import (
    VideoViewportMode,
    VideoViewportState,
)

_MIN_ZOOM = 1.0 / 64.0
_MAX_ZOOM = 64.0
_ZOOM_IN_FACTOR = 1.25
_ZOOM_OUT_FACTOR = 0.8


class VideoViewportInteraction(QObject):
    """Translate surface pointer gestures into normalized viewport state."""

    def __init__(
        self,
        *,
        surface: QWidget,
        apply_viewport: Callable[[VideoViewportState], None],
        show_fit: Callable[[], None],
        show_actual_size: Callable[[QPointF], None],
    ) -> None:
        """Observe one surface and publish bounded pan/zoom changes."""

        super().__init__(surface)
        self._surface = surface
        self._apply_viewport = apply_viewport
        self._show_fit = show_fit
        self._show_actual_size = show_actual_size
        self._state = VideoViewportState()
        self._space_held = False
        self._drag_position: QPointF | None = None
        self._last_zoom_anchor: QPointF | None = None
        surface.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        surface.installEventFilter(self)

    @property
    def state(self) -> VideoViewportState:
        """Return the current immutable viewport state."""

        return self._state

    @property
    def pan_zoom_active(self) -> bool:
        """Return whether Space currently owns temporary viewport navigation."""

        return self._space_held

    @property
    def last_zoom_anchor(self) -> QPointF | None:
        """Return the most recent wheel anchor accepted by temporary navigation."""

        return self._last_zoom_anchor

    def set_state(self, state: VideoViewportState) -> None:
        """Synchronize gestures with controller-restored geometry."""

        self._state = state
        self._refresh_cursor()

    def reset(self) -> None:
        """Restore fitted video geometry."""

        self._publish(VideoViewportState(mode=VideoViewportMode.FIT))

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Route Space-owned QPane-style navigation on the render surface."""

        if watched is not self._surface:
            return super().eventFilter(watched, event)
        if event.type() == QEvent.Type.KeyPress:
            key = cast(QKeyEvent, event)
            if key.key() == Qt.Key.Key_Space:
                if not key.isAutoRepeat():
                    self._space_held = True
                    self._refresh_cursor()
                key.accept()
                return True
        if event.type() == QEvent.Type.KeyRelease:
            key = cast(QKeyEvent, event)
            if key.key() == Qt.Key.Key_Space:
                if not key.isAutoRepeat():
                    self._end_navigation()
                key.accept()
                return True
        if event.type() in {QEvent.Type.FocusOut, QEvent.Type.Hide}:
            self._end_navigation()
            return super().eventFilter(watched, event)
        if event.type() == QEvent.Type.Wheel:
            if not self._space_held:
                return super().eventFilter(watched, event)
            wheel = cast(QWheelEvent, event)
            steps = wheel.angleDelta().y() / 120.0
            if steps:
                self._last_zoom_anchor = wheel.position()
                self._publish(
                    zoomed_viewport(
                        self._state,
                        steps=steps,
                        cursor=wheel.position(),
                        surface=self._surface,
                    )
                )
                wheel.accept()
                return True
        if event.type() == QEvent.Type.MouseButtonPress:
            if not self._space_held:
                return super().eventFilter(watched, event)
            mouse = cast(QMouseEvent, event)
            if mouse.button() == Qt.MouseButton.LeftButton:
                if self._state.zoom > 1.0:
                    self._drag_position = mouse.position()
                    self._refresh_cursor()
                return True
        if event.type() == QEvent.Type.MouseMove and self._drag_position is not None:
            mouse = cast(QMouseEvent, event)
            delta = mouse.position() - self._drag_position
            self._drag_position = mouse.position()
            self._publish(
                panned_viewport(self._state, delta=delta, surface=self._surface)
            )
            return True
        if event.type() == QEvent.Type.MouseButtonRelease:
            mouse = cast(QMouseEvent, event)
            if self._space_held and mouse.button() == Qt.MouseButton.LeftButton:
                self._drag_position = None
                self._refresh_cursor()
                return True
        if event.type() == QEvent.Type.MouseButtonDblClick:
            if not self._space_held:
                return super().eventFilter(watched, event)
            mouse = cast(QMouseEvent, event)
            if mouse.button() == Qt.MouseButton.LeftButton:
                self._drag_position = None
                if self._state.mode is VideoViewportMode.FIT:
                    self._show_actual_size(mouse.position())
                else:
                    self._show_fit()
                self._refresh_cursor()
                mouse.accept()
                return True
        return super().eventFilter(watched, event)

    def _publish(self, state: VideoViewportState) -> None:
        """Store and forward one viewport update."""

        self._state = state
        self._apply_viewport(state)
        self._refresh_cursor()

    def _end_navigation(self) -> None:
        """Clear transient Space and drag state after release or focus loss."""

        self._space_held = False
        self._drag_position = None
        self._refresh_cursor()

    def _refresh_cursor(self) -> None:
        """Mirror QPane's arrow/open-hand/closed-hand navigation feedback."""

        if not self._space_held:
            self._surface.unsetCursor()
        elif self._drag_position is not None:
            self._surface.setCursor(Qt.CursorShape.ClosedHandCursor)
        elif self._state.zoom > 1.0:
            self._surface.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self._surface.setCursor(Qt.CursorShape.ArrowCursor)


def zoomed_viewport(
    state: VideoViewportState,
    *,
    steps: float,
    cursor: QPointF,
    surface: QWidget,
) -> VideoViewportState:
    """Return cursor-anchored zoom while bounding reachable pan."""

    previous_zoom = state.zoom
    step_factor = _ZOOM_IN_FACTOR if steps > 0 else _ZOOM_OUT_FACTOR
    zoom = min(
        _MAX_ZOOM,
        max(_MIN_ZOOM, previous_zoom * (step_factor ** abs(steps))),
    )
    if zoom == previous_zoom:
        return state
    width = max(1, surface.width())
    height = max(1, surface.height())
    anchor_x = cursor.x() / width * 2.0 - 1.0
    anchor_y = cursor.y() / height * 2.0 - 1.0
    ratio = zoom / previous_zoom
    return _bounded_viewport(
        zoom,
        anchor_x - (anchor_x - state.pan_x) * ratio,
        anchor_y - (anchor_y - state.pan_y) * ratio,
        mode=VideoViewportMode.CUSTOM,
    )


def panned_viewport(
    state: VideoViewportState,
    *,
    delta: QPointF,
    surface: QWidget,
) -> VideoViewportState:
    """Return a pointer-dragged viewport in normalized surface coordinates."""

    if state.zoom <= 1.0:
        return state
    return _bounded_viewport(
        state.zoom,
        state.pan_x + delta.x() * 2.0 / max(1, surface.width()),
        state.pan_y + delta.y() * 2.0 / max(1, surface.height()),
        mode=VideoViewportMode.CUSTOM,
    )


def _bounded_viewport(
    zoom: float,
    pan_x: float,
    pan_y: float,
    *,
    mode: VideoViewportMode,
) -> VideoViewportState:
    """Clamp pan to the portion of scaled video extending past the viewport."""

    pan_limit = max(0.0, 1.0 - 1.0 / zoom)
    return VideoViewportState(
        zoom=zoom,
        pan_x=min(pan_limit, max(-pan_limit, pan_x)),
        pan_y=min(pan_limit, max(-pan_limit, pan_y)),
        mode=mode,
    )


__all__ = ["VideoViewportInteraction", "panned_viewport", "zoomed_viewport"]

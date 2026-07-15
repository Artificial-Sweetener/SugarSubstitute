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

"""Persist and clamp floating canvas geometry without canvas-domain policy."""

from __future__ import annotations

from typing import Any

from PySide6.QtGui import QGuiApplication

from substitute.application.workspace_state import WindowGeometrySnapshot

_MIN_FLOATING_CANVAS_WIDTH = 320
_MIN_FLOATING_CANVAS_HEIGHT = 240


def floating_window_display_state(window: object) -> str:
    """Return the current restorable floating-window display state."""

    is_full_screen = getattr(window, "isFullScreen", None)
    if callable(is_full_screen) and bool(is_full_screen()):
        return "fullscreen"
    is_maximized = getattr(window, "isMaximized", None)
    if callable(is_maximized) and bool(is_maximized()):
        return "maximized"
    return "normal"


def clamped_floating_geometry(
    geometry: WindowGeometrySnapshot,
) -> WindowGeometrySnapshot:
    """Return floating-window geometry clamped to available screens."""

    width = max(_MIN_FLOATING_CANVAS_WIDTH, geometry.width)
    height = max(_MIN_FLOATING_CANVAS_HEIGHT, geometry.height)
    requested = WindowGeometrySnapshot(
        x=geometry.x,
        y=geometry.y,
        width=width,
        height=height,
    )
    screens = QGuiApplication.screens()
    screen_rects = [
        screen.availableGeometry()
        for screen in screens
        if screen.availableGeometry().width() > 0
        and screen.availableGeometry().height() > 0
    ]
    if not screen_rects:
        return requested
    if any(intersects_rect(requested, rect) for rect in screen_rects):
        return requested

    primary_screen = QGuiApplication.primaryScreen()
    primary_rect = (
        primary_screen.availableGeometry()
        if primary_screen is not None
        else screen_rects[0]
    )
    max_x = primary_rect.x() + max(0, primary_rect.width() - width)
    max_y = primary_rect.y() + max(0, primary_rect.height() - height)
    return WindowGeometrySnapshot(
        x=max(primary_rect.x(), min(geometry.x, max_x)),
        y=max(primary_rect.y(), min(geometry.y, max_y)),
        width=width,
        height=height,
    )


def intersects_rect(geometry: WindowGeometrySnapshot, rect: Any) -> bool:
    """Return whether the geometry intersects a Qt-like rectangle."""

    left = geometry.x
    top = geometry.y
    right = geometry.x + geometry.width
    bottom = geometry.y + geometry.height
    rect_left = rect.x()
    rect_top = rect.y()
    rect_right = rect.x() + rect.width()
    rect_bottom = rect.y() + rect.height()
    return bool(
        max(left, rect_left) < min(right, rect_right)
        and max(
            top,
            rect_top,
        )
        < min(bottom, rect_bottom)
    )


__all__ = [
    "clamped_floating_geometry",
    "floating_window_display_state",
    "intersects_rect",
]

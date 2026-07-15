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

"""Build and restore floating canvas snapshots through generic host hooks."""

from __future__ import annotations

from typing import Any

from substitute.application.workspace_state import (
    FloatingCanvasWindowSnapshot,
    WindowGeometrySnapshot,
)
from substitute.presentation.canvas.host.geometry_persistence import (
    clamped_floating_geometry,
    floating_window_display_state,
)


def floating_canvas_snapshot(
    window: Any,
    *,
    chrome: object | None = None,
) -> FloatingCanvasWindowSnapshot:
    """Return restorable state for a floating canvas window."""

    geometry = window.geometry()
    snapshot = FloatingCanvasWindowSnapshot(
        label=str(getattr(window, "label", "")),
        geometry=WindowGeometrySnapshot(
            x=geometry.x(),
            y=geometry.y(),
            width=geometry.width(),
            height=geometry.height(),
        ),
        window_display_state=floating_window_display_state(window),
    )
    capture = getattr(chrome, "capture_snapshot", None)
    if callable(capture):
        captured = capture(snapshot)
        if isinstance(captured, FloatingCanvasWindowSnapshot):
            return captured
    return snapshot


def apply_restored_floating_snapshot(
    window: Any,
    snapshot: FloatingCanvasWindowSnapshot,
    *,
    chrome: object | None = None,
) -> None:
    """Apply restorable geometry, display state, and chrome state."""

    if snapshot.geometry is not None:
        geometry = clamped_floating_geometry(snapshot.geometry)
        window.setGeometry(
            geometry.x,
            geometry.y,
            geometry.width,
            geometry.height,
        )
    display_state = snapshot.window_display_state
    if display_state == "fullscreen":
        window.showFullScreen()
    elif display_state == "maximized":
        window.showMaximized()
    elif display_state == "normal":
        show_normal = getattr(window, "showNormal", None)
        if callable(show_normal):
            show_normal()
    restore = getattr(chrome, "restore_snapshot", None)
    if callable(restore):
        restore(snapshot)


__all__ = [
    "apply_restored_floating_snapshot",
    "floating_canvas_snapshot",
]

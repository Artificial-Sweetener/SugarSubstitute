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

"""Host compact Input tool chrome over the canvas without reserving a rail."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QWidget
from substitute.presentation.canvas.shared.canvas_chrome_metrics import (
    CANVAS_CHROME_GAP,
    CANVAS_CHROME_OVERLAY_INSET,
)
from substitute.presentation.canvas.shared.canvas_top_bar import CanvasTopBar
from substitute.presentation.canvas.tools import (
    CanvasToolLayout,
    CanvasToolOptionsHost,
    CanvasToolRuntime,
    CanvasToolStrip,
)


class InputCanvasToolChrome:
    """Coordinate the Input tool strip and contextual option surface."""

    def __init__(
        self,
        *,
        canvas: QWidget,
        tool_requested: Callable[[str], None],
    ) -> None:
        """Create a content-sized strip parented directly over the canvas."""

        self._host_obstacles: tuple[QRect, ...] = ()
        self._suppressed = False
        self.tool_strip = CanvasToolStrip(canvas)
        self.tool_strip.move(
            CANVAS_CHROME_OVERLAY_INSET,
            CANVAS_CHROME_OVERLAY_INSET,
        )
        self.tool_strip.toolRequested.connect(tool_requested)
        self.top_bar = CanvasTopBar(canvas)
        self.options_host = CanvasToolOptionsHost(self.top_bar)
        self.top_bar.append_control(self.options_host)
        self.options_host.surfaceChanged.connect(self._synchronize_chrome)
        self.top_bar.geometryChanged.connect(self.sync_geometry)

    def bind_runtime(
        self,
        runtime: CanvasToolRuntime,
        layout: CanvasToolLayout | None = None,
    ) -> None:
        """Bind one live runtime to tool buttons and contextual options."""

        self.tool_strip.bind_palette(runtime.palette, layout)
        self.options_host.bind_runtime(runtime)
        self._synchronize_chrome()
        self.tool_strip.raise_()

    def set_enabled(self, enabled: bool) -> None:
        """Apply canvas availability to the overlay controls."""

        self.tool_strip.setEnabled(enabled)
        self.options_host.setEnabled(enabled)

    def set_suppressed(self, suppressed: bool) -> None:
        """Hide normal editor chrome while an exclusive control owns the canvas."""
        suppressed = bool(suppressed)
        if suppressed == self._suppressed:
            return
        self._suppressed = suppressed
        if suppressed:
            self.tool_strip.hide()
            self.top_bar.hide()
            return
        self.tool_strip.setVisible(bool(self.tool_strip.tool_buttons()))
        self.top_bar.synchronize_geometry()
        self.sync_geometry()

    def set_host_obstacles(self, obstacles: tuple[QRect, ...]) -> None:
        """Arrange Input-owned chrome around host-owned overlay rectangles."""

        self._host_obstacles = tuple(QRect(obstacle) for obstacle in obstacles)
        self.sync_geometry()

    def sync_geometry(self) -> None:
        """Position ordered top chrome and the vertical rail without collisions."""

        if self._suppressed:
            self.tool_strip.hide()
            self.top_bar.hide()
            return

        if self.top_bar.isVisible():
            self.top_bar.move(self._top_bar_origin())
            self.top_bar.raise_()
        obstacles = self._host_obstacles
        if self.top_bar.isVisible():
            obstacles += (self.top_bar.geometry(),)
        origin = self._unobstructed_tool_origin(obstacles)
        self.tool_strip.move(origin)
        self.tool_strip.raise_()

    def _synchronize_chrome(self) -> None:
        """Project child visibility and intrinsic size before positioning chrome."""

        if self._suppressed:
            self.tool_strip.hide()
            self.top_bar.hide()
            return
        self.top_bar.synchronize_geometry()
        self.sync_geometry()

    def _top_bar_origin(self) -> QPoint:
        """Place Input top-bar controls after intersecting host-owned chrome."""

        candidate = QRect(
            CANVAS_CHROME_OVERLAY_INSET,
            CANVAS_CHROME_OVERLAY_INSET,
            self.top_bar.width(),
            self.top_bar.height(),
        )
        for obstacle in sorted(self._host_obstacles, key=lambda bounds: bounds.left()):
            if candidate.intersects(obstacle):
                candidate.moveLeft(obstacle.right() + 1 + CANVAS_CHROME_GAP)
        return candidate.topLeft()

    def _unobstructed_tool_origin(self, obstacles: tuple[QRect, ...]) -> QPoint:
        """Place the Input tool rail below every intersecting top surface."""

        candidate = QRect(
            CANVAS_CHROME_OVERLAY_INSET,
            CANVAS_CHROME_OVERLAY_INSET,
            self.tool_strip.width(),
            self.tool_strip.height(),
        )
        for obstacle in sorted(obstacles, key=lambda bounds: bounds.top()):
            if candidate.intersects(obstacle):
                candidate.moveTop(obstacle.bottom() + 1 + CANVAS_CHROME_GAP)
        return candidate.topLeft()


__all__ = ["InputCanvasToolChrome"]

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

"""Synchronize the editor's visible-cube signal from mounted geometry."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from PySide6.QtCore import QPoint
from shiboken6 import isValid

from .cube_reveal_geometry import CubeRevealGeometryResolver


class VisibleCubeSignalProtocol(Protocol):
    """Describe the visible-cube signal boundary."""

    def emit(self, route_key: str) -> None:
        """Emit one visible cube route key."""


class VisibleCubeScrollPort(Protocol):
    """Describe visible scroll coordinates used by synchronization."""

    def widget(self) -> object | None:
        """Return the scroll content widget."""

    def visible_content_top(self) -> int:
        """Return the visible content top coordinate."""

    def visible_content_bottom(self) -> int:
        """Return the visible content bottom coordinate."""


class VisibleCubeSyncHost(Protocol):
    """Describe mounted order and signal state used by synchronization."""

    scroll: VisibleCubeScrollPort
    _stack_order: Sequence[str] | None
    currentCubeVisibleChanged: VisibleCubeSignalProtocol


class VisibleCubeSynchronizer:
    """Publish the leading visible cube without owning navigation state."""

    def __init__(
        self,
        host: VisibleCubeSyncHost,
        geometry: CubeRevealGeometryResolver,
    ) -> None:
        """Store the mounted host and shared geometry resolver."""

        self._host = host
        self._geometry = geometry

    def synchronize(self, *, programmatic_route_key: str | None = None) -> None:
        """Publish a navigation target or the leading cube in the viewport."""

        if programmatic_route_key is not None:
            self.emit(programmatic_route_key)
            return
        if not self._host._stack_order:
            return

        scroll_content = self._host.scroll.widget()
        if scroll_content is None:
            return
        visible_y = self._host.scroll.visible_content_top()
        visible_bottom = self._host.scroll.visible_content_bottom()
        first_visible_cube: str | None = None
        best_y: int | None = None

        for alias in self._host._stack_order:
            widget = self._geometry.cube_widget(alias)
            if widget is None or not isValid(widget):
                continue
            position_y = widget.mapTo(scroll_content, QPoint(0, 0)).y()
            if position_y + widget.height() < visible_y or position_y > visible_bottom:
                continue
            if best_y is None or position_y < best_y:
                best_y = position_y
                first_visible_cube = alias

        if first_visible_cube is not None:
            self.emit(first_visible_cube)

    def emit(self, route_key: str) -> None:
        """Emit the route key when the host signal remains available."""

        signal = getattr(self._host, "currentCubeVisibleChanged", None)
        emit = getattr(signal, "emit", None)
        if callable(emit):
            emit(route_key)


__all__ = ["VisibleCubeSyncHost", "VisibleCubeSynchronizer"]

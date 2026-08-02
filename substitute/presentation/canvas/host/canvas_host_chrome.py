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

"""Compose host-owned canvas selection with canvas-owned overlay controls."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QWidget

from substitute.presentation.canvas.host.canvas_host_selector import (
    CanvasHostSelector,
)
from substitute.presentation.canvas.host.canvas_host_state import CanvasHostState


@runtime_checkable
class CanvasHostChromeParticipant(Protocol):
    """Arrange canvas-owned controls around host-owned overlay geometry."""

    def set_host_chrome_obstacles(self, obstacles: tuple[QRect, ...]) -> None:
        """Arrange canvas-owned chrome without intersecting host surfaces."""


class CanvasHostChrome:
    """Own selector presentation and per-canvas overlay clearance."""

    def __init__(
        self,
        parent: QWidget,
        *,
        selected_callback: Callable[[str], None],
    ) -> None:
        """Create host chrome over the stack without reserving a permanent rail."""

        self.selector = CanvasHostSelector(
            parent,
            selected_callback=selected_callback,
        )

    def synchronize(self, state: CanvasHostState) -> None:
        """Project host state and geometry into selector and canvas-owned chrome."""

        self.selector.present(state)
        obstacles = () if self.selector.isHidden() else (self.selector.geometry(),)
        for entry in state:
            participant = entry.page.widget
            if isinstance(participant, CanvasHostChromeParticipant):
                participant.set_host_chrome_obstacles(
                    obstacles if entry.attached else ()
                )


__all__ = ["CanvasHostChrome", "CanvasHostChromeParticipant"]

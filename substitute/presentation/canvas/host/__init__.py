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

"""Host docked and floating canvas pages without canvas-domain policy."""

from __future__ import annotations

from substitute.presentation.canvas.host.canvas_availability_presenter import (
    CanvasAvailabilityPresenter,
)
from substitute.presentation.canvas.host.canvas_focus_controller import (
    CanvasFocusController,
)
from substitute.presentation.canvas.host.canvas_tabs_view import (
    CanvasHostPage,
    CanvasTabManager,
    DockablePivotItem,
    create_canvas_host,
)
from substitute.presentation.canvas.host.floating_canvas_window import (
    FloatingCanvasChrome,
    FloatingCanvasWindow,
)

__all__ = [
    "CanvasAvailabilityPresenter",
    "CanvasFocusController",
    "CanvasHostPage",
    "CanvasTabManager",
    "DockablePivotItem",
    "FloatingCanvasChrome",
    "FloatingCanvasWindow",
    "create_canvas_host",
]

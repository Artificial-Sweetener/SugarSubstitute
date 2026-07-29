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

"""Typing surface for the public Input canvas widget API."""

from __future__ import annotations

from uuid import UUID

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget
from cutecanvas import CuteCanvas, ExecutionRuntime
from sugarsubstitute_shared.localization import ApplicationText

from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteSessionBoundaryPort,
    InputRouteProjectorPort,
)
from substitute.presentation.canvas.tools import CanvasToolPalette, CanvasToolStrip
from substitute.presentation.canvas.input.input_document import InputCanvasDocument

class InputCanvas(QWidget):
    """Expose host-facing Input canvas widget controls and intent signals."""

    inputMaskSaved: Signal
    inputImageLoaded: Signal
    toolContextRefreshRequested: Signal
    toolRequested: Signal
    dockActionRequested: Signal
    document: InputCanvasDocument
    canvas: CuteCanvas

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        execution_runtime: ExecutionRuntime | None = None,
        route_session_boundary: CanvasRouteSessionBoundaryPort | None = None,
    ) -> None: ...
    @property
    def route_projector(self) -> InputRouteProjectorPort:
        """Return the authorized Input route projector for this widget."""
        ...

    def current_image_id_for_event(self) -> UUID | None:
        """Return the event image ID exposed by the route projector."""
        ...

    def set_available(
        self,
        available: bool,
        reason: ApplicationText = "",
    ) -> None:
        """Set active-workflow Input canvas availability presentation."""
        ...

    def set_canvas_detached(self, detached: bool) -> None:
        """Set manager-owned canvas attachment state."""
        ...

    @property
    def tool_strip(self) -> CanvasToolStrip:
        """Return the compact tool overlay."""
        ...

    def bind_tool_palette(self, palette: CanvasToolPalette) -> None:
        """Bind the contextual Input tool palette."""
        ...

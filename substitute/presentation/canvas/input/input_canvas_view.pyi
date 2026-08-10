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

from PySide6.QtCore import QRect, Signal
from PySide6.QtWidgets import QWidget
from cutecanvas import CuteCanvas, ExecutionRuntime
from sugarsubstitute_shared.localization import ApplicationText

from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteSessionBoundaryPort,
    InputRouteProjectorPort,
)
from substitute.presentation.canvas.shared.canvas_top_bar import CanvasTopBar
from substitute.presentation.canvas.shared.contextual_toolbar import (
    CanvasContextualToolbar,
)
from substitute.presentation.canvas.tools import (
    CanvasToolLayout,
    CanvasToolOptionsHost,
    CanvasToolRuntime,
    CanvasToolStrip,
)
from substitute.presentation.canvas.input.input_document import InputCanvasDocument
from substitute.presentation.canvas.input.input_layer_coverage_editor import (
    InputLayerCoverageEditor,
)

class InputCanvas(QWidget):
    """Expose host-facing Input canvas widget controls and intent signals."""

    inputImageLoaded: Signal
    toolRequested: Signal
    dockActionRequested: Signal
    document: InputCanvasDocument
    canvas: CuteCanvas
    contextual_toolbar: CanvasContextualToolbar

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
        """Set host-owned canvas attachment state."""
        ...

    def set_host_chrome_obstacles(self, obstacles: tuple[QRect, ...]) -> None:
        """Arrange Input tool chrome around host-owned overlay surfaces."""
        ...

    @property
    def tool_strip(self) -> CanvasToolStrip:
        """Return the compact tool overlay."""
        ...

    @property
    def tool_options_host(self) -> CanvasToolOptionsHost:
        """Return the contextual top-bar options host."""
        ...

    @property
    def canvas_top_bar(self) -> CanvasTopBar:
        """Return the ordered Input-owned top-bar flow."""
        ...

    @property
    def coverage_editor(self) -> InputLayerCoverageEditor:
        """Return the exclusive bottom coverage editor."""
        ...

    @property
    def coverage_edit_active(self) -> bool:
        """Return whether layer coverage preview exclusively owns the canvas."""
        ...

    def bind_tool_runtime(
        self,
        runtime: CanvasToolRuntime,
        layout: CanvasToolLayout | None = ...,
    ) -> None:
        """Bind the contextual Input tool runtime."""
        ...

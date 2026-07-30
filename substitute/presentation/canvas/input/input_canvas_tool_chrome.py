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

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QWidget
from qfluentwidgets import MenuAnimationType  # type: ignore[import-untyped]

from substitute.presentation.canvas.input.input_canvas_tool_menu import (
    create_input_canvas_tool_menu,
)
from substitute.presentation.canvas.tools import (
    CanvasToolOptionsPanel,
    CanvasToolRuntime,
    CanvasToolStrip,
)
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer

_TOOL_STRIP_INSET = 8


class InputCanvasToolChrome:
    """Coordinate Input tool strip and context menu from one palette."""

    def __init__(
        self,
        *,
        canvas: QWidget,
        tool_requested: Callable[[str], None],
        context_refresh_requested: Callable[[], None],
        dock_requested: Callable[[], None],
        detached_provider: Callable[[], bool],
    ) -> None:
        """Create a content-sized strip parented directly over the canvas."""

        self._canvas = canvas
        self._tool_requested = tool_requested
        self._context_refresh_requested = context_refresh_requested
        self._dock_requested = dock_requested
        self._detached_provider = detached_provider
        self._runtime: CanvasToolRuntime | None = None
        self.tool_strip = CanvasToolStrip(canvas)
        self.tool_strip.move(_TOOL_STRIP_INSET, _TOOL_STRIP_INSET)
        self.tool_strip.toolRequested.connect(self._tool_requested)
        self.options_panel = CanvasToolOptionsPanel(canvas)
        self.options_panel.surfaceChanged.connect(self.sync_geometry)

    def bind_runtime(self, runtime: CanvasToolRuntime) -> None:
        """Bind one live runtime to tool buttons and contextual options."""

        self._runtime = runtime
        self.tool_strip.bind_palette(runtime.palette)
        self.options_panel.bind_runtime(runtime)
        self.sync_geometry()
        self.tool_strip.raise_()

    def set_enabled(self, enabled: bool) -> None:
        """Apply canvas availability to the overlay controls."""

        self.tool_strip.setEnabled(enabled)
        self.options_panel.setEnabled(enabled)

    def sync_geometry(self) -> None:
        """Keep content-sized options adjacent without reserving canvas space."""

        self.tool_strip.move(_TOOL_STRIP_INSET, _TOOL_STRIP_INSET)
        self.options_panel.move(
            self.tool_strip.geometry().right() + _TOOL_STRIP_INSET,
            _TOOL_STRIP_INSET,
        )
        self.tool_strip.raise_()
        if self.options_panel.isVisible():
            self.options_panel.raise_()

    def show_context_menu(self, position: QPoint) -> None:
        """Refresh context and show a menu from the strip's palette snapshot."""

        self._context_refresh_requested()
        runtime = self._runtime
        if runtime is None:
            return
        model = create_input_canvas_tool_menu(
            runtime.palette.snapshot(),
            tool_requested=self._tool_requested,
            detached=self._detached_provider(),
            dock_requested=self._dock_requested,
        )
        menu = QFluentMenuRenderer(parent=self._canvas).render(model)
        menu.exec(
            self._canvas.mapToGlobal(position),
            aniType=MenuAnimationType.DROP_DOWN,
        )


__all__ = ["InputCanvasToolChrome"]

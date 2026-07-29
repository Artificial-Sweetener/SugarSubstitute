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

"""Route CuteCanvas context requests to the Output action set they require."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from cutecanvas import CanvasPresentationKind

from .output_canvas_context_menu import OutputCanvasContextMenu
from .output_grid_context_menu import OutputGridContextMenu


@dataclass(frozen=True, slots=True, weakref_slot=True)
class OutputContextMenuRouter:
    """Keep the established Output menu separate from addressed grid actions."""

    presentation_kind: Callable[[], CanvasPresentationKind]
    output_menu: OutputCanvasContextMenu
    grid_menu: OutputGridContextMenu

    def show(self, subject: object, global_position: object) -> None:
        """Route grid targets to addressed actions and all else to Output actions."""

        if self.presentation_kind() is CanvasPresentationKind.GRID:
            self.grid_menu.show(subject, global_position)
            return
        self.output_menu.show(global_position)


__all__ = ["OutputContextMenuRouter"]

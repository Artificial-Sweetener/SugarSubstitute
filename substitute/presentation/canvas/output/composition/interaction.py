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

"""Compose Output pointer interaction collaborators."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from substitute.presentation.canvas.output.output_canvas_interaction_controller import (
    GridPoint,
    OutputCanvasInteractionController,
)


def output_interaction_controller_for_host(
    host: object,
    *,
    set_control_mode: Callable[[object], None],
    cursor_control_mode: object,
    panzoom_control_mode: object,
) -> OutputCanvasInteractionController:
    """Return the pointer interaction controller wired to an Output canvas host."""

    return OutputCanvasInteractionController(
        press_position=lambda: cast(
            GridPoint | None,
            getattr(host, "_grid_click_press_pos", None),
        ),
        set_press_position=lambda position: setattr(
            host,
            "_grid_click_press_pos",
            position,
        ),
        set_control_mode=set_control_mode,
        cursor_control_mode=cursor_control_mode,
        panzoom_control_mode=panzoom_control_mode,
    )

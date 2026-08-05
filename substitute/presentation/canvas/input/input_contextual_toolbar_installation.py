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

"""Install Input-owned actions presented by the Contextual Toolbar."""

from __future__ import annotations

from substitute.presentation.canvas.tools import CanvasToolRuntime

from .input_canvas_tool_catalog import (
    clear_selection_pixels_contribution,
    deselect_contribution,
)
from .input_tool_options_contracts import InputToolOptionsDocumentPort


def install_input_contextual_toolbar(
    runtime: CanvasToolRuntime,
    document: InputToolOptionsDocumentPort,
) -> None:
    """Register selection actions against their authoritative document adapter."""
    runtime.register_action(
        deselect_contribution(),
        document.clear_pixel_selection,
    )
    runtime.register_action(
        clear_selection_pixels_contribution(),
        document.clear_selected_pixels,
    )


__all__ = ["install_input_contextual_toolbar"]

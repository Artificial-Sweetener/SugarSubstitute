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

"""Own Input canvas presentation surface and controllers."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from substitute.presentation.canvas.input.input_canvas_presenter import (
        InputCanvasPresenter,
    )
    from substitute.presentation.canvas.input.input_canvas_view import InputCanvas
    from substitute.presentation.canvas.input.input_canvas_tool_controller import (
        InputCanvasToolController,
    )
    from substitute.presentation.canvas.input.input_canvas_tool_profile_controller import (
        InputCanvasToolProfileController,
    )

_EXPORT_MODULES = {
    "InputCanvas": "substitute.presentation.canvas.input.input_canvas_view",
    "InputCanvasPresenter": (
        "substitute.presentation.canvas.input.input_canvas_presenter"
    ),
    "InputCanvasToolController": (
        "substitute.presentation.canvas.input.input_canvas_tool_controller"
    ),
    "InputCanvasToolProfileController": (
        "substitute.presentation.canvas.input.input_canvas_tool_profile_controller"
    ),
}

__all__ = [
    "InputCanvas",
    "InputCanvasPresenter",
    "InputCanvasToolController",
    "InputCanvasToolProfileController",
]


def __getattr__(name: str) -> object:
    """Load public input-canvas exports only when callers request them."""

    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Return stable lazy-export names for interactive inspection."""

    return sorted({*globals(), *__all__})

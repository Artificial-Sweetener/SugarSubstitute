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

"""Canvas presentation widgets and dockable host composition."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from substitute.presentation.canvas.factory import (
        create_canvas_tabs,
        create_output_floating_chrome_factory,
    )
    from substitute.presentation.canvas.host import CanvasTabManager
    from substitute.presentation.canvas.input.input_canvas_view import InputCanvas
    from substitute.presentation.canvas.output.output_canvas_view import OutputCanvas
    from substitute.presentation.canvas.output.output_linked_group_presenter import (
        OutputLinkedGroupPresenter,
    )

_EXPORT_MODULES = {
    "CanvasTabManager": "substitute.presentation.canvas.host",
    "InputCanvas": "substitute.presentation.canvas.input.input_canvas_view",
    "OutputCanvas": "substitute.presentation.canvas.output.output_canvas_view",
    "OutputLinkedGroupPresenter": (
        "substitute.presentation.canvas.output.output_linked_group_presenter"
    ),
    "create_canvas_tabs": "substitute.presentation.canvas.factory",
    "create_output_floating_chrome_factory": "substitute.presentation.canvas.factory",
}

__all__ = [
    "CanvasTabManager",
    "InputCanvas",
    "OutputCanvas",
    "OutputLinkedGroupPresenter",
    "create_canvas_tabs",
    "create_output_floating_chrome_factory",
]


def __getattr__(name: str) -> object:
    """Load public canvas exports only when callers request them."""

    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Return stable lazy-export names for interactive inspection."""

    return sorted({*globals(), *__all__})

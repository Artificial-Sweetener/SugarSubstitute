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

"""Expose reusable runtime canvas-tool presentation primitives."""

from .layout import (
    CanvasToolGroupSlot,
    CanvasToolLayout,
    CanvasToolLayoutSnapshot,
    create_canvas_tool_layout,
)
from .layout_codec import CanvasToolLayoutCodec
from .model import (
    CanvasToolContext,
    CanvasToolContribution,
    CanvasToolKind,
    CanvasToolPresentation,
    CanvasToolSurface,
)
from .palette import CanvasToolPalette
from .registry import CanvasToolRegistry
from .runtime import (
    CanvasToolAction,
    CanvasToolOptionsFactory,
    CanvasToolProvider,
    CanvasToolProviderSnapshot,
    CanvasToolRuntime,
)
from .tool_strip import CanvasToolStrip
from .tool_options_control import CanvasToolOptionsControl
from .tool_options_host import CanvasToolOptionsHost

__all__ = [
    "CanvasToolGroupSlot",
    "CanvasToolLayout",
    "CanvasToolLayoutCodec",
    "CanvasToolLayoutSnapshot",
    "CanvasToolContext",
    "CanvasToolContribution",
    "CanvasToolKind",
    "CanvasToolPalette",
    "CanvasToolPresentation",
    "CanvasToolSurface",
    "CanvasToolRegistry",
    "CanvasToolAction",
    "CanvasToolOptionsFactory",
    "CanvasToolProvider",
    "CanvasToolProviderSnapshot",
    "CanvasToolRuntime",
    "CanvasToolStrip",
    "CanvasToolOptionsControl",
    "CanvasToolOptionsHost",
    "create_canvas_tool_layout",
]

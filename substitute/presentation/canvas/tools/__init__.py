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

from .model import (
    CanvasToolContext,
    CanvasToolContribution,
    CanvasToolKind,
    CanvasToolPresentation,
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
from .tool_options_panel import CanvasToolOptionsPanel

__all__ = [
    "CanvasToolContext",
    "CanvasToolContribution",
    "CanvasToolKind",
    "CanvasToolPalette",
    "CanvasToolPresentation",
    "CanvasToolRegistry",
    "CanvasToolAction",
    "CanvasToolOptionsFactory",
    "CanvasToolProvider",
    "CanvasToolProviderSnapshot",
    "CanvasToolRuntime",
    "CanvasToolStrip",
    "CanvasToolOptionsPanel",
]

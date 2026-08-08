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

"""Define application-owned synthetic canvas resize intent."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from substitute.domain.workflow.input_canvas_plan import CanvasDimensions


class SyntheticCanvasResizeScope(StrEnum):
    """Select whether pixels are retained or resampled with canvas bounds."""

    CANVAS_ONLY = "canvas_only"
    CANVAS_AND_LAYERS = "canvas_and_layers"


class SyntheticCanvasAnchor(StrEnum):
    """Select the fixed point for a canvas-only bounds resize."""

    TOP_LEFT = "top-left"
    TOP = "top"
    TOP_RIGHT = "top-right"
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    BOTTOM_LEFT = "bottom-left"
    BOTTOM = "bottom"
    BOTTOM_RIGHT = "bottom-right"


class SyntheticCanvasResamplingMode(StrEnum):
    """Select the layer pixel resampling quality."""

    FAST = "fast"
    SMOOTH = "smooth"


@dataclass(frozen=True, slots=True)
class SyntheticCanvasResizeRequest:
    """Carry validated user intent across presentation and canvas adapters."""

    dimensions: CanvasDimensions
    scope: SyntheticCanvasResizeScope = SyntheticCanvasResizeScope.CANVAS_ONLY
    anchor: SyntheticCanvasAnchor = SyntheticCanvasAnchor.CENTER
    resampling_mode: SyntheticCanvasResamplingMode = (
        SyntheticCanvasResamplingMode.SMOOTH
    )


__all__ = [
    "SyntheticCanvasAnchor",
    "SyntheticCanvasResamplingMode",
    "SyntheticCanvasResizeRequest",
    "SyntheticCanvasResizeScope",
]

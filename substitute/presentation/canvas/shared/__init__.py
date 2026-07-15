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

"""Expose shared canvas presentation helpers used by Input and Output owners."""

from __future__ import annotations

from substitute.presentation.canvas.shared.canvas_grid_layout import (
    CanvasGridLayout,
    grid_layout_for_dimensions,
)
from substitute.presentation.canvas.shared.canvas_nav_picker import (
    CanvasNavPicker,
    CanvasNavPickerItem,
)
from substitute.presentation.canvas.shared.output_nav_layout import (
    OutputCompareNavGeometry,
    OutputNavBarGeometry,
    OutputNavControlWidths,
    compare_navigation_geometry,
    navigation_bar_width,
)
from substitute.presentation.canvas.shared.output_set_picker import OutputSetPicker
from substitute.presentation.canvas.shared.types import OutputImageMeta

__all__ = [
    "CanvasGridLayout",
    "CanvasNavPicker",
    "CanvasNavPickerItem",
    "OutputCompareNavGeometry",
    "OutputImageMeta",
    "OutputNavBarGeometry",
    "OutputNavControlWidths",
    "OutputSetPicker",
    "compare_navigation_geometry",
    "grid_layout_for_dimensions",
    "navigation_bar_width",
]

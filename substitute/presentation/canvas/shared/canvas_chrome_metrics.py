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

"""Define shared geometry tokens for floating canvas chrome composition."""

from __future__ import annotations

CANVAS_CHROME_CONTROL_HEIGHT = 28
CANVAS_CHROME_SURFACE_PADDING = 4
CANVAS_CHROME_SURFACE_BORDER_WIDTH = 1
CANVAS_CHROME_SURFACE_HEIGHT = CANVAS_CHROME_CONTROL_HEIGHT + (
    2 * CANVAS_CHROME_SURFACE_PADDING
)
CANVAS_CHROME_OVERLAY_INSET = 8
CANVAS_CHROME_GAP = 8
CONTEXTUAL_TOOLBAR_REANCHOR_PHYSICAL_PX = 64
CONTEXTUAL_TOOLBAR_EDGE_HYSTERESIS_PHYSICAL_PX = 24

__all__ = [
    "CANVAS_CHROME_CONTROL_HEIGHT",
    "CANVAS_CHROME_GAP",
    "CANVAS_CHROME_OVERLAY_INSET",
    "CANVAS_CHROME_SURFACE_BORDER_WIDTH",
    "CANVAS_CHROME_SURFACE_HEIGHT",
    "CANVAS_CHROME_SURFACE_PADDING",
    "CONTEXTUAL_TOOLBAR_EDGE_HYSTERESIS_PHYSICAL_PX",
    "CONTEXTUAL_TOOLBAR_REANCHOR_PHYSICAL_PX",
]

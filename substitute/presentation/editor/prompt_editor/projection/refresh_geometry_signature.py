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

"""Describe prompt surface visual state relevant to geometry refresh."""

from __future__ import annotations

from dataclasses import dataclass

from ..core.projection.document import PromptProjectionDisplayMode
from .freshness_controller import ProjectionFreshness


@dataclass(frozen=True, slots=True)
class PromptRefreshGeometryPaintSignature:
    """Identify whether a geometry refresh changes visible paint state."""

    content_height: float
    content_width: float
    viewport_width: int
    viewport_height: int
    scroll_value: int
    scroll_maximum: int
    page_step: int
    display_mode: PromptProjectionDisplayMode
    projection_freshness: ProjectionFreshness
    source_line_content_left_inset: float
    source_line_chrome_enabled: bool
    font_key: str
    palette_key: int


__all__ = ["PromptRefreshGeometryPaintSignature"]

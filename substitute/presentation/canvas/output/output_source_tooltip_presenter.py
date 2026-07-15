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

"""Build Output source-tab tooltip text from projection metadata."""

from __future__ import annotations

from substitute.application.generation import format_generation_duration
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasSourceGroup,
)


def source_tab_tooltip_text(
    source: OutputCanvasSourceGroup,
    *,
    active_set_index: int,
) -> str:
    """Return tooltip text for one Output source tab."""

    item = source.nearest_item(max(1, active_set_index))
    if item is None:
        return ""

    metadata = item.image_meta
    lines: list[str] = []
    width = getattr(metadata, "width", None)
    height = getattr(metadata, "height", None)
    if isinstance(width, int) and width > 0 and isinstance(height, int) and height > 0:
        lines.append(f"{width}x{height}")

    duration_text = format_generation_duration(
        getattr(metadata, "cube_execution_duration_ms", None)
    )
    if duration_text:
        lines.append(duration_text)
    return "\n".join(lines)


__all__ = ["source_tab_tooltip_text"]

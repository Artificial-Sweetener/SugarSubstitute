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

"""Define strict visual identity for immutable prompt reorder chip geometry."""

from __future__ import annotations

from .reorder_chip_geometry import PromptReorderChipGeometry


def chip_geometry_visual_reuse_key(
    geometry: PromptReorderChipGeometry,
) -> tuple[object, ...]:
    """Return every geometry input that must match for visual object reuse."""

    return (
        geometry.chip_index,
        geometry.source_start,
        geometry.source_end,
        geometry.rendered_start,
        geometry.rendered_end,
        geometry.geometry_id.visual_revision,
        geometry.hotspot_rect.left(),
        geometry.hotspot_rect.top(),
        geometry.hotspot_rect.width(),
        geometry.hotspot_rect.height(),
        round(geometry.outline_bounds.left(), 3),
        round(geometry.outline_bounds.top(), 3),
        round(geometry.outline_bounds.width(), 3),
        round(geometry.outline_bounds.height(), 3),
        tuple(
            (
                line.visual_line_index,
                round(line.content_rect.left(), 3),
                round(line.content_rect.top(), 3),
                round(line.content_rect.width(), 3),
                round(line.content_rect.height(), 3),
                round(line.leading_anchor.x(), 3),
                round(line.leading_anchor.y(), 3),
                round(line.trailing_anchor.x(), 3),
                round(line.trailing_anchor.y(), 3),
            )
            for line in geometry.visual_lines
        ),
    )


__all__ = ["chip_geometry_visual_reuse_key"]

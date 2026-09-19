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

"""Project the progressively replaced batch shown by Automatic Output focus."""

from __future__ import annotations

from uuid import UUID

from substitute.application.workflows.output_canvas_projection_model import (
    OutputCanvasImageItem,
    OutputCanvasSourceGroup,
)


def automatic_frontier_items(
    sources: tuple[OutputCanvasSourceGroup, ...],
    *,
    source_key: str,
) -> tuple[OutputCanvasImageItem, ...]:
    """Fill the active CubeOutput's pending batch slots from preceding outputs.

    A downstream CubeOutput replaces a batch position only when that position
    becomes presentable. This keeps the rest of the preceding complete batch
    visible while a single preview or an incomplete final batch arrives.
    """

    frontier_by_set: dict[int, OutputCanvasImageItem] = {}
    found_source = False
    for source in sources:
        frontier_by_set.update(source.images_by_set)
        if source.source_key == source_key:
            found_source = True
            break
    if not found_source:
        return ()
    return tuple(frontier_by_set[index] for index in sorted(frontier_by_set))


def automatic_frontier_image_ids(
    sources: tuple[OutputCanvasSourceGroup, ...],
    *,
    source_key: str,
) -> tuple[UUID, ...]:
    """Return the Automatic progressive batch in visual position order."""

    return tuple(
        item.image_id
        for item in automatic_frontier_items(sources, source_key=source_key)
    )


__all__ = ["automatic_frontier_image_ids", "automatic_frontier_items"]

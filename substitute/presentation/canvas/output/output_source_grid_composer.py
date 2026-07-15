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

"""Select source-batch tiles and delegate responsive scene construction."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_canvas_route_scope import (
    source_grid_route_identity,
)
from substitute.presentation.canvas.output.output_grid_scene_builder import (
    OutputGridSceneBuilder,
    OutputGridScenePlan,
    OutputGridTile,
)
from substitute.presentation.canvas.shared.responsive_canvas_grid_policy import (
    CanvasViewportExtent,
)

_OUTPUT_GRID_LAYER_NAMESPACE = UUID("cc916abe-75c7-48ca-adc5-7a3dc3ff4c74")


class OutputSourceGridComposer:
    """Select ordered final-output tiles for one source batch."""

    def __init__(
        self,
        payload_lookup: Callable[[UUID], object | None],
        *,
        scene_builder: OutputGridSceneBuilder,
        viewport_extent: Callable[[], CanvasViewportExtent],
    ) -> None:
        """Store payload, generic builder, and physical viewport providers."""

        self._payload_lookup = payload_lookup
        self._scene_builder = scene_builder
        self._viewport_extent = viewport_extent

    def compose_source_grid(
        self,
        source: OutputCanvasSourceGroup,
        *,
        scene_key: str | None,
        previous_dimensions: tuple[int, int] | None = None,
        viewport_extent: CanvasViewportExtent | None = None,
    ) -> OutputGridScenePlan | None:
        """Build a responsive source-grid scene plan when tiles are available."""

        route = source_grid_route_identity(
            source_key=source.source_key, active_scene_key=scene_key
        )
        tiles = self._tiles_for_source(source, route.route_key)
        if not tiles:
            return None
        return self._scene_builder.build(
            route=route,
            title=f"{source.label} grid",
            tiles=tiles,
            viewport_extent=viewport_extent or self._viewport_extent(),
            previous_dimensions=previous_dimensions,
        )

    def _tiles_for_source(
        self, source: OutputCanvasSourceGroup, route_key: str
    ) -> tuple[OutputGridTile, ...]:
        """Return payload-backed source tiles ordered by set index."""

        tiles: list[OutputGridTile] = []
        for item in sorted(
            source.images_by_set.values(), key=lambda candidate: candidate.set_index
        ):
            image = self._payload_lookup(item.image_id)
            if image is None:
                continue
            metadata: dict[str, object] = {
                "grid_kind": "batch",
                "source_key": source.source_key,
                "source_label": source.label,
                "set_index": item.set_index,
                "image_id": str(item.image_id),
                "kind": "final-output",
                "preview": False,
            }
            tiles.append(
                OutputGridTile(
                    image_id=item.image_id,
                    image=image,
                    layer_namespace=_OUTPUT_GRID_LAYER_NAMESPACE,
                    layer_identity_seed=(
                        f"source-grid;route:{route_key};image:{item.image_id}"
                    ),
                    role="final-output",
                    metadata=metadata,
                    content_key=(
                        "batch",
                        source.source_key,
                        source.label,
                        item.set_index,
                        str(item.image_id),
                    ),
                )
            )
        return tuple(tiles)


__all__ = ["OutputSourceGridComposer"]

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

"""Select scene-overview tiles and delegate responsive scene construction."""

from __future__ import annotations

from collections.abc import Callable, Container, Mapping
from dataclasses import dataclass
from uuid import UUID

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasSceneGroup,
)
from substitute.application.workflows.output_canvas_route_scope import (
    scene_overview_route_identity,
)
from substitute.application.workflows.output_preview_lifecycle_service import (
    PreviewSlotKey,
    ScenePreviewSlot,
    preview_slot_for_scene,
)
from substitute.presentation.canvas.output.output_grid_scene_builder import (
    OutputGridSceneBuilder,
    OutputGridScenePlan,
    OutputGridTile,
)
from substitute.presentation.canvas.shared.responsive_canvas_grid_policy import (
    CanvasViewportExtent,
)

_OUTPUT_SCENE_LAYER_NAMESPACE = UUID("018c32cc-e16f-47d2-8892-c576169de566")


@dataclass(frozen=True, slots=True)
class OutputSceneOverviewPreview:
    """Describe a transient preview accepted as one scene overview tile."""

    image_id: UUID
    image: object
    source_key: str
    set_index: int


class OutputSceneOverviewComposer:
    """Select ordered preview-or-final tiles for the scene overview."""

    def __init__(
        self,
        *,
        payload_lookup: Callable[[UUID], object | None],
        scene_builder: OutputGridSceneBuilder,
        viewport_extent: Callable[[], CanvasViewportExtent],
        preview_lookup: Callable[
            [OutputCanvasSceneGroup], OutputSceneOverviewPreview | None
        ]
        | None = None,
    ) -> None:
        """Store final, preview, generic builder, and viewport collaborators."""

        self._payload_lookup = payload_lookup
        self._preview_lookup = preview_lookup
        self._scene_builder = scene_builder
        self._viewport_extent = viewport_extent

    def compose_scene_overview(
        self,
        scenes: tuple[OutputCanvasSceneGroup, ...],
        *,
        active_scene_key: str | None,
        previous_dimensions: tuple[int, int] | None = None,
        viewport_extent: CanvasViewportExtent | None = None,
    ) -> OutputGridScenePlan | None:
        """Build a responsive scene-overview plan when visual tiles exist."""

        route = scene_overview_route_identity(active_scene_key=active_scene_key)
        tiles = self._tiles_for_scenes(scenes, route.route_key)
        if not tiles:
            return None
        return self._scene_builder.build(
            route=route,
            title="All scenes",
            tiles=tiles,
            viewport_extent=viewport_extent or self._viewport_extent(),
            previous_dimensions=previous_dimensions,
        )

    def _tiles_for_scenes(
        self, scenes: tuple[OutputCanvasSceneGroup, ...], route_key: str
    ) -> tuple[OutputGridTile, ...]:
        """Return scene tiles ordered by stable display order and key."""

        tiles: list[OutputGridTile] = []
        for scene in sorted(
            scenes, key=lambda candidate: (candidate.order, candidate.scene_key)
        ):
            preview = self._preview_lookup(scene) if self._preview_lookup else None
            if preview is not None:
                tiles.append(
                    self._tile(
                        scene=scene,
                        route_key=route_key,
                        image_id=preview.image_id,
                        image=preview.image,
                        preview=True,
                        source_key=preview.source_key,
                        set_index=preview.set_index,
                    )
                )
                continue
            if scene.primary_image_id is None:
                continue
            image = self._payload_lookup(scene.primary_image_id)
            if image is None:
                continue
            tiles.append(
                self._tile(
                    scene=scene,
                    route_key=route_key,
                    image_id=scene.primary_image_id,
                    image=image,
                    preview=False,
                    source_key=scene.representative_source_key,
                    set_index=scene.representative_set_index,
                )
            )
        return tuple(tiles)

    @staticmethod
    def _tile(
        *,
        scene: OutputCanvasSceneGroup,
        route_key: str,
        image_id: UUID,
        image: object,
        preview: bool,
        source_key: str | None,
        set_index: int | None,
    ) -> OutputGridTile:
        """Build one generic scene tile with stable hit-test metadata."""

        kind = "preview" if preview else "final-output"
        metadata: dict[str, object] = {
            "grid_kind": "scene",
            "scene_run_id": scene.scene_run_id,
            "scene_key": scene.scene_key,
            "scene_title": scene.title,
            "scene_order": scene.order,
            "image_id": str(image_id),
            "kind": kind,
            "preview": preview,
            "representative_source_key": source_key,
            "representative_set_index": set_index,
        }
        return OutputGridTile(
            image_id=image_id,
            image=image,
            layer_namespace=_OUTPUT_SCENE_LAYER_NAMESPACE,
            layer_identity_seed=(
                f"scene-overview;route:{route_key};scene:{scene.scene_key};image:{image_id}"
            ),
            role="scene-output",
            metadata=metadata,
            content_key=(
                "scene",
                scene.scene_run_id,
                scene.scene_key,
                scene.title,
                scene.order,
                str(image_id),
                preview,
                source_key,
                set_index,
            ),
        )


def scene_overview_preview_for_scene(
    scene: OutputCanvasSceneGroup,
    *,
    preview_image_cache: Mapping[UUID, object],
    scene_preview_slots: Mapping[str, ScenePreviewSlot],
    completed_preview_slots: Container[PreviewSlotKey],
) -> OutputSceneOverviewPreview | None:
    """Return a composer-ready accepted preview tile for one scene."""

    preview_slot = preview_slot_for_scene(
        scene=scene,
        preview_slot=scene_preview_slots.get(scene.scene_key),
        cached_preview_ids=preview_image_cache.keys(),
        completed_preview_slots=completed_preview_slots,
    )
    if preview_slot is None:
        return None
    image = preview_image_cache.get(preview_slot.preview_id)
    if image is None:
        return None
    return OutputSceneOverviewPreview(
        image_id=preview_slot.preview_id,
        image=image,
        source_key=preview_slot.source_key,
        set_index=preview_slot.set_index,
    )


__all__ = [
    "OutputSceneOverviewComposer",
    "OutputSceneOverviewPreview",
    "scene_overview_preview_for_scene",
]

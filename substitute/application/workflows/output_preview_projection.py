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

"""Project live previews as transient Output source/set placeholders."""

from __future__ import annotations

from collections.abc import Iterable

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewLane,
    OutputPreviewLanePlacement,
)
from substitute.domain.workflow import ImageMeta


def overlay_preview_sources(
    final_sources: Iterable[OutputCanvasSourceGroup],
    preview_lanes: Iterable[OutputPreviewLane],
    *,
    scene_key: str | None,
) -> tuple[OutputCanvasSourceGroup, ...]:
    """Overlay set-one preview slots while preserving final source and set order."""

    sources = list(final_sources)
    source_indices = {source.source_key: index for index, source in enumerate(sources)}
    for lane in _source_view_lanes(preview_lanes, scene_key=scene_key):
        source_index = source_indices.get(lane.key.source_key)
        preview_item = _preview_item(lane)
        if source_index is None:
            source_indices[lane.key.source_key] = len(sources)
            sources.append(
                OutputCanvasSourceGroup(
                    source_key=lane.key.source_key,
                    label=lane.source_label or lane.key.source_key,
                    images_by_set={1: preview_item},
                )
            )
            continue
        current = sources[source_index]
        images_by_set = dict(current.images_by_set)
        images_by_set[1] = preview_item
        sources[source_index] = OutputCanvasSourceGroup(
            source_key=current.source_key,
            label=current.label,
            images_by_set=images_by_set,
            label_is_default=current.label_is_default,
        )
    return tuple(sources)


def overlay_preview_scenes(
    final_scenes: Iterable[OutputCanvasSceneGroup],
    preview_lanes: Iterable[OutputPreviewLane],
) -> tuple[OutputCanvasSceneGroup, ...]:
    """Overlay preview representatives and source placeholders into scene groups."""

    lanes = tuple(preview_lanes)
    scenes = list(final_scenes)
    scene_indices = {scene.scene_key: index for index, scene in enumerate(scenes)}
    scene_lanes: dict[str, list[OutputPreviewLane]] = {}
    for lane in lanes:
        if (
            lane.key.placement is OutputPreviewLanePlacement.SCENE
            and lane.key.scene_key is not None
        ):
            scene_lanes.setdefault(lane.key.scene_key, []).append(lane)
    for scene_key, representatives in scene_lanes.items():
        scene_index = scene_indices.get(scene_key)
        final = scenes[scene_index] if scene_index is not None else None
        representative = _representative_lane(final, representatives)
        sources = overlay_preview_sources(
            () if final is None else final.sources,
            lanes,
            scene_key=scene_key,
        )
        overlaid = OutputCanvasSceneGroup(
            scene_run_id=(
                representative.key.scene_run_id
                or (final.scene_run_id if final is not None else "")
            ),
            scene_key=scene_key,
            title=(
                representative.scene_title
                or (final.title if final is not None else scene_key)
            ),
            order=(
                representative.scene_order
                if representative.scene_order is not None
                else (final.order if final is not None else len(scenes))
            ),
            sources=sources,
            preview_image_id=representative.preview_id,
            primary_image_id=final.primary_image_id if final is not None else None,
            representative_source_key=representative.key.source_key,
            representative_set_index=1,
            status="running",
            title_is_default=final.title_is_default if final is not None else False,
        )
        if scene_index is None:
            scene_indices[scene_key] = len(scenes)
            scenes.append(overlaid)
        else:
            scenes[scene_index] = overlaid
    return tuple(sorted(scenes, key=lambda scene: scene.order))


def _source_view_lanes(
    preview_lanes: Iterable[OutputPreviewLane],
    *,
    scene_key: str | None,
) -> tuple[OutputPreviewLane, ...]:
    """Choose one source-view lane per source for the requested scene scope."""

    selected: dict[str, OutputPreviewLane] = {}
    for lane in preview_lanes:
        if lane.key.scene_key != scene_key:
            continue
        current = selected.get(lane.key.source_key)
        if current is None or (
            current.key.placement is OutputPreviewLanePlacement.SCENE
            and lane.key.placement is OutputPreviewLanePlacement.SOURCE
        ):
            selected[lane.key.source_key] = lane
    return tuple(selected.values())


def _preview_item(lane: OutputPreviewLane) -> OutputCanvasImageItem:
    """Represent one live lane as the first batch slot of its eventual output."""

    source_label = lane.source_label or lane.key.source_key
    return OutputCanvasImageItem(
        image_id=lane.preview_id,
        image_meta=ImageMeta(
            workflow_name=lane.key.workflow_id,
            cube_name=source_label,
            image_number=1,
            suffix="",
            path="",
            source_key=lane.key.source_key,
            source_label=source_label,
            generation_run_id=lane.key.generation_run_id,
            prompt_id=lane.key.prompt_id,
            client_id=lane.client_id,
            scene_run_id=lane.key.scene_run_id or "",
            scene_key=lane.key.scene_key or "",
            scene_title=lane.scene_title or "",
            scene_order=lane.scene_order,
            scene_count=lane.scene_count,
            batch_index=0,
        ),
        set_index=1,
    )


def _representative_lane(
    final_scene: OutputCanvasSceneGroup | None,
    lanes: list[OutputPreviewLane],
) -> OutputPreviewLane:
    """Choose the furthest-progressed preview without regressing on late frames."""

    source_order = (
        {source.source_key: index for index, source in enumerate(final_scene.sources)}
        if final_scene is not None
        else {}
    )
    return max(
        lanes,
        key=lambda lane: source_order.get(
            lane.key.source_key,
            len(source_order) + lanes.index(lane),
        ),
    )


__all__ = ["overlay_preview_scenes", "overlay_preview_sources"]

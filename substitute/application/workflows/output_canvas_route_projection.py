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

"""Resolve one authoritative Output route from populated projection content."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from substitute.application.workflows.output_automatic_frontier_projection import (
    automatic_frontier_items,
)
from substitute.application.workflows.output_canvas_projection_model import (
    OutputCanvasImageItem,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.domain.workflow import ImageMeta, OutputFocusMode, WorkflowState


@dataclass(frozen=True, slots=True)
class OutputCanvasResolvedRoute:
    """Describe the route selected from currently presentable Output content."""

    scene_count: int
    active_scene_key: str | None
    active_scene_overview: bool
    active_source_key: str | None
    active_set_index: int
    active_uuid: UUID | None


def resolve_output_canvas_route(
    workflow: WorkflowState,
    *,
    sources: tuple[OutputCanvasSourceGroup, ...],
    scene_groups: tuple[OutputCanvasSceneGroup, ...],
    image_meta_map: Mapping[UUID, ImageMeta],
) -> OutputCanvasResolvedRoute:
    """Select the least-specific populated route unless the user chose one."""

    scene_count = len(scene_groups)
    active_scene_key = _active_scene_key_for_workflow(
        workflow,
        scene_groups,
        image_meta_map,
    )
    active_scene = _scene_for_key(scene_groups, active_scene_key)
    focus_sources = (
        active_scene.sources
        if scene_count > 1 and active_scene is not None
        else sources
    )
    automatic_source_key = _latest_source_key_for_workflow(workflow, focus_sources)
    active_scene_overview = _active_scene_overview_for_workflow(
        workflow,
        scene_count=scene_count,
    )
    if active_scene_overview:
        active_source_key, active_set_index, active_uuid = None, 1, None
    elif scene_count > 1 and active_scene_key is not None:
        active_source_key, active_set_index, active_uuid = _active_projection_focus(
            workflow=workflow,
            sources=focus_sources,
            items_by_uuid=_items_by_uuid_for_sources(focus_sources),
            automatic_source_key=automatic_source_key,
        )
    else:
        active_source_key, active_set_index, active_uuid = _active_projection_focus(
            workflow=workflow,
            sources=sources,
            items_by_uuid=_items_by_uuid_for_sources(sources),
            automatic_source_key=automatic_source_key,
        )
    return OutputCanvasResolvedRoute(
        scene_count=scene_count,
        active_scene_key=active_scene_key,
        active_scene_overview=active_scene_overview,
        active_source_key=active_source_key,
        active_set_index=active_set_index,
        active_uuid=active_uuid,
    )


def _active_scene_overview_for_workflow(
    workflow: WorkflowState,
    *,
    scene_count: int,
) -> bool:
    """Keep Automatic on All once more than one scene is presentable."""

    if scene_count <= 1:
        return False
    if workflow.output_focus_mode == OutputFocusMode.MANUAL:
        return workflow.active_output_scene_overview
    return True


def _active_scene_key_for_workflow(
    workflow: WorkflowState,
    scene_groups: tuple[OutputCanvasSceneGroup, ...],
    image_meta_map: Mapping[UUID, ImageMeta],
) -> str | None:
    """Return the best active populated scene key for workflow focus state."""

    if workflow.output_focus_mode == OutputFocusMode.MANUAL:
        scene = _scene_for_key(scene_groups, workflow.active_output_scene_key)
        if scene is not None:
            return scene.scene_key
    latest_scene_key = _latest_scene_key_for_workflow(workflow, image_meta_map)
    if _scene_for_key(scene_groups, latest_scene_key) is not None:
        return latest_scene_key
    uuid_scene_key = _active_scene_key_for_uuid(
        workflow.active_output_uuid,
        image_meta_map,
    )
    if _scene_for_key(scene_groups, uuid_scene_key) is not None:
        return uuid_scene_key
    return scene_groups[0].scene_key if scene_groups else None


def _latest_scene_key_for_workflow(
    workflow: WorkflowState,
    image_meta_map: Mapping[UUID, ImageMeta],
) -> str | None:
    """Return the scene key for the newest workflow Output."""

    for image_id in reversed(workflow.output_image_uuids):
        image_meta = image_meta_map.get(image_id)
        if image_meta is not None and image_meta.scene_key:
            return image_meta.scene_key
    return None


def _scene_for_key(
    scene_groups: tuple[OutputCanvasSceneGroup, ...],
    scene_key: str | None,
) -> OutputCanvasSceneGroup | None:
    """Return a populated scene group by key."""

    if scene_key is None:
        return None
    for scene in scene_groups:
        if scene.scene_key == scene_key:
            return scene
    return None


def _items_by_uuid_for_sources(
    sources: tuple[OutputCanvasSourceGroup, ...],
) -> dict[UUID, tuple[str, OutputCanvasImageItem]]:
    """Build focus lookup from already scoped source groups."""

    items_by_uuid: dict[UUID, tuple[str, OutputCanvasImageItem]] = {}
    for source in sources:
        for item in source.images_by_set.values():
            items_by_uuid[item.image_id] = (source.source_key, item)
    return items_by_uuid


def _active_projection_focus(
    *,
    workflow: WorkflowState,
    sources: tuple[OutputCanvasSourceGroup, ...],
    items_by_uuid: Mapping[UUID, tuple[str, OutputCanvasImageItem]],
    automatic_source_key: str | None,
) -> tuple[str | None, int, UUID | None]:
    """Resolve active source/batch focus from user intent or automatic follow."""

    if not sources:
        return None, 1, None
    if workflow.output_focus_mode == OutputFocusMode.MANUAL:
        if workflow.active_output_set_index == 0:
            return _manual_grid_focus(workflow, sources)
        return _manual_concrete_focus(workflow, sources, items_by_uuid)
    return _automatic_focus(sources, preferred_source_key=automatic_source_key)


def _automatic_focus(
    sources: tuple[OutputCanvasSourceGroup, ...],
    *,
    preferred_source_key: str | None,
) -> tuple[str | None, int, UUID | None]:
    """Promote the newest populated source to its least-specific useful route."""

    source = _source_for_key(sources, preferred_source_key) or sources[-1]
    frontier = automatic_frontier_items(sources, source_key=source.source_key)
    if len(frontier) > 1:
        return source.source_key, 0, None
    return _focus_for_source(source)


def _latest_source_key_for_workflow(
    workflow: WorkflowState,
    sources: tuple[OutputCanvasSourceGroup, ...],
) -> str | None:
    """Return the source containing the newest projected workflow image."""

    source_by_image_id = {
        item.image_id: source.source_key
        for source in sources
        for item in source.images_by_set.values()
    }
    for image_id in reversed(workflow.output_image_uuids):
        source_key = source_by_image_id.get(image_id)
        if source_key is not None:
            return source_key
    return None


def _manual_concrete_focus(
    workflow: WorkflowState,
    sources: tuple[OutputCanvasSourceGroup, ...],
    items_by_uuid: Mapping[UUID, tuple[str, OutputCanvasImageItem]],
) -> tuple[str | None, int, UUID | None]:
    """Preserve a user-selected concrete Output with deterministic fallback."""

    active_uuid = workflow.active_output_uuid
    item_entry = items_by_uuid.get(active_uuid) if active_uuid is not None else None
    if item_entry is not None:
        source_key, selected_item = item_entry
        return source_key, selected_item.set_index, selected_item.image_id
    if workflow.active_output_source_key:
        source = _source_for_key(sources, workflow.active_output_source_key)
        if source is not None:
            exact_item = source.images_by_set.get(workflow.active_output_set_index)
            if exact_item is not None:
                return source.source_key, exact_item.set_index, exact_item.image_id
    return _first_concrete_focus(sources)


def _manual_grid_focus(
    workflow: WorkflowState,
    sources: tuple[OutputCanvasSourceGroup, ...],
) -> tuple[str | None, int, UUID | None]:
    """Preserve a user-selected populated grid with concrete fallback."""

    source = (
        _source_for_key(sources, workflow.active_output_source_key)
        if workflow.active_output_source_key
        else None
    )
    if source is not None:
        if source.images_by_set:
            return source.source_key, 0, None
        item = source.first_item()
        if item is not None:
            return source.source_key, item.set_index, item.image_id
    return _first_concrete_focus(sources)


def _focus_for_source(
    source: OutputCanvasSourceGroup,
) -> tuple[str | None, int, UUID | None]:
    """Return the least-specific useful route for one populated source."""

    if len(source.images_by_set) > 1:
        return source.source_key, 0, None
    item = source.first_item()
    if item is None:
        return source.source_key, 1, None
    return source.source_key, item.set_index, item.image_id


def _first_concrete_focus(
    sources: tuple[OutputCanvasSourceGroup, ...],
) -> tuple[str | None, int, UUID | None]:
    """Return the first available concrete Output focus."""

    for source in sources:
        item = source.first_item()
        if item is not None:
            return source.source_key, item.set_index, item.image_id
    return None, 1, None


def _source_for_key(
    sources: tuple[OutputCanvasSourceGroup, ...],
    source_key: str | None,
) -> OutputCanvasSourceGroup | None:
    """Return a source group by key."""

    if source_key is None:
        return None
    for source in sources:
        if source.source_key == source_key:
            return source
    return None


def _active_scene_key_for_uuid(
    image_id: UUID | None,
    image_meta_map: Mapping[UUID, ImageMeta],
) -> str | None:
    """Return scene key for an active Output UUID when present."""

    if image_id is None:
        return None
    image_meta = image_meta_map.get(image_id)
    if image_meta is None or not image_meta.scene_key:
        return None
    return image_meta.scene_key


__all__ = ["OutputCanvasResolvedRoute", "resolve_output_canvas_route"]

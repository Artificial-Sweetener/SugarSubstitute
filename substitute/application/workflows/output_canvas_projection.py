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

"""Build grouped output-canvas projections from workflow image state."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from substitute.domain.workflow import (
    ImageMeta,
    OutputCompareState,
    OutputFocusMode,
    WorkflowState,
)


@dataclass(frozen=True)
class OutputCanvasImageItem:
    """Describe one selectable output image in a source/set grid."""

    image_id: UUID
    image_meta: ImageMeta
    set_index: int


@dataclass(frozen=True)
class OutputCanvasSourceGroup:
    """Describe one output-producing source rendered as an output tab."""

    source_key: str
    label: str
    images_by_set: Mapping[int, OutputCanvasImageItem]

    def nearest_item(self, preferred_set_index: int) -> OutputCanvasImageItem | None:
        """Return the nearest image item to a requested set index."""

        if not self.images_by_set:
            return None
        if preferred_set_index in self.images_by_set:
            return self.images_by_set[preferred_set_index]
        nearest_set = min(
            self.images_by_set,
            key=lambda set_index: (
                abs(set_index - preferred_set_index),
                set_index,
            ),
        )
        return self.images_by_set[nearest_set]


@dataclass(frozen=True)
class OutputCanvasSceneGroup:
    """Describe one prompt scene grouping rendered above source and batch."""

    scene_run_id: str
    scene_key: str
    title: str
    order: int
    sources: tuple[OutputCanvasSourceGroup, ...]
    preview_image_id: UUID | None = None
    primary_image_id: UUID | None = None
    representative_source_key: str | None = None
    representative_set_index: int | None = None
    status: str = "completed"


@dataclass(frozen=True)
class OutputCanvasProjection:
    """Describe the output canvas selector state for one workflow."""

    sources: tuple[OutputCanvasSourceGroup, ...]
    active_source_key: str | None
    active_set_index: int
    active_uuid: UUID | None
    set_count: int
    scene_groups: tuple[OutputCanvasSceneGroup, ...] = ()
    active_scene_key: str | None = None
    active_scene_overview: bool = False
    scene_count: int = 0
    compare_state: OutputCompareState = OutputCompareState()

    def source_for_key(self, source_key: str) -> OutputCanvasSourceGroup | None:
        """Return source group for a stable source key when available."""

        for source in self.sources:
            if source.source_key == source_key:
                return source
        return None

    def item_for(
        self,
        *,
        source_key: str,
        set_index: int,
    ) -> OutputCanvasImageItem | None:
        """Return the best item for a source/set selection."""

        source = self.source_for_key(source_key)
        if source is None:
            return None
        return source.nearest_item(set_index)

    def first_item_for_set(self, set_index: int) -> OutputCanvasImageItem | None:
        """Return the first source item for one set index when available."""

        for source in self.sources:
            item = source.images_by_set.get(set_index)
            if item is not None:
                return item
        return None


def build_output_canvas_projection(
    workflow: WorkflowState,
    image_meta_map: Mapping[UUID, ImageMeta],
) -> OutputCanvasProjection:
    """Return grouped output-canvas presentation state for a workflow."""

    projection_items = _projection_items(workflow, image_meta_map)
    sources, set_count, items_by_uuid = _source_groups_for_items(projection_items)
    scene_groups = _scene_groups_for_items(projection_items)
    scene_count = _scene_count_for_items(projection_items, scene_groups)
    active_scene_key = _active_scene_key_for_workflow(
        workflow,
        scene_groups,
        image_meta_map,
    )
    active_scene_overview = _active_scene_overview_for_workflow(
        workflow,
        scene_count=scene_count,
    )
    if active_scene_overview:
        active_source_key, active_set_index, active_uuid = None, 1, None
    elif scene_count > 1 and active_scene_key is not None:
        scene = _scene_for_key(scene_groups, active_scene_key)
        focus_sources = scene.sources if scene is not None else ()
        active_source_key, active_set_index, active_uuid = _active_projection_focus(
            workflow=workflow,
            sources=focus_sources,
            items_by_uuid=_items_by_uuid_for_sources(focus_sources),
        )
    else:
        active_source_key, active_set_index, active_uuid = _active_projection_focus(
            workflow=workflow,
            sources=sources,
            items_by_uuid=items_by_uuid,
        )

    projection = OutputCanvasProjection(
        sources=sources,
        active_source_key=active_source_key,
        active_set_index=active_set_index,
        active_uuid=active_uuid,
        set_count=set_count,
        scene_groups=scene_groups,
        active_scene_key=active_scene_key,
        active_scene_overview=active_scene_overview,
        scene_count=scene_count,
        compare_state=workflow.output_compare_state,
    )
    return projection


def _projection_items(
    workflow: WorkflowState,
    image_meta_map: Mapping[UUID, ImageMeta],
) -> tuple[tuple[UUID, ImageMeta], ...]:
    """Return output image metadata in workflow display order."""

    items: list[tuple[UUID, ImageMeta]] = []
    for image_id in workflow.output_image_uuids:
        image_meta = image_meta_map.get(image_id)
        if image_meta is not None:
            items.append((image_id, image_meta))
    return tuple(items)


def _source_groups_for_items(
    image_items: tuple[tuple[UUID, ImageMeta], ...],
) -> tuple[
    tuple[OutputCanvasSourceGroup, ...],
    int,
    dict[UUID, tuple[str, OutputCanvasImageItem]],
]:
    """Return source groups, max set count, and image focus lookup for items."""

    grouped_items: OrderedDict[str, list[tuple[UUID, ImageMeta]]] = OrderedDict()
    source_labels: dict[str, str] = {}
    for image_id, image_meta in image_items:
        source_key = _source_key_for(image_id, image_meta)
        grouped_items.setdefault(source_key, []).append((image_id, image_meta))
        source_labels.setdefault(source_key, _source_label_for(image_meta))

    sources: list[OutputCanvasSourceGroup] = []
    set_count = 0
    items_by_uuid: dict[UUID, tuple[str, OutputCanvasImageItem]] = {}

    for source_key, source_image_items in grouped_items.items():
        images_by_set: dict[int, OutputCanvasImageItem] = {}
        fallback_index = 1
        for image_id, image_meta in source_image_items:
            if image_meta.list_index is None:
                continue
            set_index = image_meta.list_index + 1
            item = OutputCanvasImageItem(
                image_id=image_id,
                image_meta=image_meta,
                set_index=set_index,
            )
            images_by_set[set_index] = item
            items_by_uuid[image_id] = (source_key, item)
        for image_id, image_meta in source_image_items:
            if image_meta.list_index is not None:
                continue
            if _has_backend_routing_identity(image_meta):
                continue
            while fallback_index in images_by_set:
                fallback_index += 1
            item = OutputCanvasImageItem(
                image_id=image_id,
                image_meta=image_meta,
                set_index=fallback_index,
            )
            images_by_set[fallback_index] = item
            items_by_uuid[image_id] = (source_key, item)
            fallback_index += 1
        if not images_by_set:
            continue
        set_count = max(set_count, max(images_by_set, default=0))
        sources.append(
            OutputCanvasSourceGroup(
                source_key=source_key,
                label=source_labels[source_key],
                images_by_set=images_by_set,
            )
        )

    return tuple(sources), set_count, items_by_uuid


def _scene_groups_for_items(
    image_items: tuple[tuple[UUID, ImageMeta], ...],
) -> tuple[OutputCanvasSceneGroup, ...]:
    """Return prompt-scene groups in scene order for output items."""

    grouped_items: OrderedDict[str, list[tuple[UUID, ImageMeta]]] = OrderedDict()
    scene_run_ids: dict[str, str] = {}
    scene_titles: dict[str, str] = {}
    scene_orders: dict[str, int] = {}
    for image_id, image_meta in image_items:
        scene_key = _scene_key_for(image_meta)
        grouped_items.setdefault(scene_key, []).append((image_id, image_meta))
        scene_run_ids.setdefault(scene_key, image_meta.scene_run_id)
        scene_titles.setdefault(scene_key, _scene_title_for(image_meta))
        scene_orders.setdefault(scene_key, _scene_order_for(image_meta))

    groups: list[OutputCanvasSceneGroup] = []
    for scene_key, grouped_scene_items in grouped_items.items():
        sources, _set_count, _items_by_uuid = _source_groups_for_items(
            tuple(grouped_scene_items)
        )
        representative_source_key, representative_set_index, primary_image_id = (
            _scene_representative_for_sources(sources)
        )
        groups.append(
            OutputCanvasSceneGroup(
                scene_run_id=scene_run_ids[scene_key],
                scene_key=scene_key,
                title=scene_titles[scene_key],
                order=scene_orders[scene_key],
                sources=sources,
                primary_image_id=primary_image_id,
                representative_source_key=representative_source_key,
                representative_set_index=representative_set_index,
            )
        )
    return tuple(sorted(groups, key=lambda group: (group.order, group.scene_key)))


def _scene_representative_for_sources(
    sources: tuple[OutputCanvasSourceGroup, ...],
) -> tuple[str | None, int | None, UUID | None]:
    """Return the terminal scene source, set index, and representative image id."""

    for source in reversed(sources):
        item = source.nearest_item(1)
        if item is not None:
            return source.source_key, item.set_index, item.image_id
    return None, None, None


def _scene_count_for_items(
    image_items: tuple[tuple[UUID, ImageMeta], ...],
    scene_groups: tuple[OutputCanvasSceneGroup, ...],
) -> int:
    """Return declared scene count when available, otherwise visible scene groups."""

    declared_scene_counts = [
        image_meta.scene_count
        for _image_id, image_meta in image_items
        if image_meta.scene_count is not None and image_meta.scene_count > 0
    ]
    if declared_scene_counts:
        return max(declared_scene_counts)
    return len(scene_groups)


def _active_scene_overview_for_workflow(
    workflow: WorkflowState,
    *,
    scene_count: int,
) -> bool:
    """Return whether projection should activate the scene overview."""

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
    """Return the best active scene key for workflow focus state."""

    if workflow.output_focus_mode == OutputFocusMode.MANUAL:
        scene = _scene_for_key(scene_groups, workflow.active_output_scene_key)
        if scene is not None:
            return scene.scene_key
    uuid_scene_key = _active_scene_key_for_uuid(
        workflow.active_output_uuid,
        image_meta_map,
    )
    if _scene_for_key(scene_groups, uuid_scene_key) is not None:
        return uuid_scene_key
    latest_scene_key = _latest_scene_key_for_workflow(workflow, image_meta_map)
    if _scene_for_key(scene_groups, latest_scene_key) is not None:
        return latest_scene_key
    return scene_groups[0].scene_key if scene_groups else None


def _latest_scene_key_for_workflow(
    workflow: WorkflowState,
    image_meta_map: Mapping[UUID, ImageMeta],
) -> str | None:
    """Return scene key for the newest workflow output with scene metadata."""

    for image_id in reversed(workflow.output_image_uuids):
        image_meta = image_meta_map.get(image_id)
        if image_meta is not None and image_meta.scene_key:
            return image_meta.scene_key
    return None


def _scene_for_key(
    scene_groups: tuple[OutputCanvasSceneGroup, ...],
    scene_key: str | None,
) -> OutputCanvasSceneGroup | None:
    """Return a scene group by key."""

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
) -> tuple[str | None, int, UUID | None]:
    """Resolve active output focus from workflow intent and available sources."""

    if not sources:
        return None, 1, None
    if workflow.output_focus_mode == OutputFocusMode.MANUAL:
        if workflow.active_output_set_index == 0:
            focus = _manual_grid_focus(workflow, sources)
        else:
            focus = _manual_concrete_focus(workflow, sources, items_by_uuid)
    else:
        focus = _automatic_focus(workflow, sources, items_by_uuid)
    return focus


def _automatic_focus(
    workflow: WorkflowState,
    sources: tuple[OutputCanvasSourceGroup, ...],
    items_by_uuid: Mapping[UUID, tuple[str, OutputCanvasImageItem]],
) -> tuple[str | None, int, UUID | None]:
    """Resolve automatic focus, promoting multi-output sources to grid mode."""

    source: OutputCanvasSourceGroup | None = None
    active_uuid = workflow.active_output_uuid
    item_entry = items_by_uuid.get(active_uuid) if active_uuid is not None else None
    if item_entry is not None:
        source_key, _selected_item = item_entry
        source = _source_for_key(sources, source_key)
    if source is None and workflow.active_output_source_key:
        source = _source_for_key(sources, workflow.active_output_source_key)
    if source is None:
        source = _latest_source(workflow, sources, items_by_uuid) or sources[0]
    return _focus_for_source(source)


def _manual_concrete_focus(
    workflow: WorkflowState,
    sources: tuple[OutputCanvasSourceGroup, ...],
    items_by_uuid: Mapping[UUID, tuple[str, OutputCanvasImageItem]],
) -> tuple[str | None, int, UUID | None]:
    """Resolve user-selected concrete output focus with deterministic fallback."""

    active_uuid = workflow.active_output_uuid
    item_entry = items_by_uuid.get(active_uuid) if active_uuid is not None else None
    if item_entry is not None:
        source_key, selected_item = item_entry
        return source_key, selected_item.set_index, selected_item.image_id
    if workflow.active_output_source_key:
        source = _source_for_key(sources, workflow.active_output_source_key)
        if source is not None:
            nearest_item = source.nearest_item(workflow.active_output_set_index)
            if nearest_item is not None:
                return source.source_key, nearest_item.set_index, nearest_item.image_id
    return _first_concrete_focus(sources)


def _manual_grid_focus(
    workflow: WorkflowState,
    sources: tuple[OutputCanvasSourceGroup, ...],
) -> tuple[str | None, int, UUID | None]:
    """Resolve user-selected grid focus with concrete fallback when unavailable."""

    source = (
        _source_for_key(sources, workflow.active_output_source_key)
        if workflow.active_output_source_key
        else None
    )
    if source is not None:
        if _source_has_grid(source):
            return source.source_key, 0, None
        item = source.nearest_item(1)
        if item is not None:
            return source.source_key, item.set_index, item.image_id
    return _first_concrete_focus(sources)


def _focus_for_source(
    source: OutputCanvasSourceGroup,
) -> tuple[str | None, int, UUID | None]:
    """Return grid or concrete focus for one source according to its item count."""

    if _source_has_grid(source):
        return source.source_key, 0, None
    item = source.nearest_item(1)
    if item is None:
        return source.source_key, 1, None
    return source.source_key, item.set_index, item.image_id


def _first_concrete_focus(
    sources: tuple[OutputCanvasSourceGroup, ...],
) -> tuple[str | None, int, UUID | None]:
    """Return the first available concrete output focus."""

    for source in sources:
        item = source.nearest_item(1)
        if item is not None:
            return source.source_key, item.set_index, item.image_id
    return None, 1, None


def _latest_source(
    workflow: WorkflowState,
    sources: tuple[OutputCanvasSourceGroup, ...],
    items_by_uuid: Mapping[UUID, tuple[str, OutputCanvasImageItem]],
) -> OutputCanvasSourceGroup | None:
    """Return the source for the newest valid output in workflow order."""

    for image_id in reversed(workflow.output_image_uuids):
        item_entry = items_by_uuid.get(image_id)
        if item_entry is None:
            continue
        source_key, _item = item_entry
        source = _source_for_key(sources, source_key)
        if source is not None:
            return source
    return None


def _source_for_key(
    sources: tuple[OutputCanvasSourceGroup, ...],
    source_key: str | None,
) -> OutputCanvasSourceGroup | None:
    """Return a source group by key from a projection source tuple."""

    if source_key is None:
        return None
    for source in sources:
        if source.source_key == source_key:
            return source
    return None


def _source_has_grid(source: OutputCanvasSourceGroup) -> bool:
    """Return whether a source has enough finished outputs for grid set zero."""

    return len(source.images_by_set) > 1


def _source_key_for(image_id: UUID, image_meta: ImageMeta) -> str:
    """Return stable grouping identity for one output image."""

    if image_meta.source_key:
        return image_meta.source_key
    if image_meta.cube_name:
        return image_meta.cube_name
    return str(image_id)


def _source_label_for(image_meta: ImageMeta) -> str:
    """Return display label for one output source group."""

    if image_meta.source_label:
        return image_meta.source_label
    if image_meta.cube_name:
        return image_meta.cube_name
    return "Output"


def _has_backend_routing_identity(image_meta: ImageMeta) -> bool:
    """Return whether metadata carries any backend final-output identity."""

    return any(
        (
            image_meta.generation_run_id,
            image_meta.prompt_id,
            image_meta.client_id,
            image_meta.node_id,
        )
    )


def _scene_key_for(image_meta: ImageMeta) -> str:
    """Return stable scene grouping key for one output image."""

    if image_meta.scene_key:
        return image_meta.scene_key
    return ""


def _scene_title_for(image_meta: ImageMeta) -> str:
    """Return scene display title for one output image."""

    if image_meta.scene_title:
        return image_meta.scene_title
    return "Scene"


def _scene_order_for(image_meta: ImageMeta) -> int:
    """Return scene display order for one output image."""

    if image_meta.scene_order is not None:
        return image_meta.scene_order
    return 0


def _active_scene_key_for_uuid(
    active_uuid: UUID | None,
    image_meta_map: Mapping[UUID, ImageMeta],
) -> str | None:
    """Return the active scene key for one concrete active image."""

    if active_uuid is None:
        return None
    image_meta = image_meta_map.get(active_uuid)
    if image_meta is None or not image_meta.scene_key:
        return None
    return image_meta.scene_key


__all__ = [
    "OutputCanvasImageItem",
    "OutputCanvasProjection",
    "OutputCanvasSceneGroup",
    "OutputCanvasSourceGroup",
    "build_output_canvas_projection",
]

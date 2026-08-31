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
from uuid import UUID

from sugarsubstitute_shared.localization import (
    ApplicationText,
    app_text,
    opaque_text,
    render_source_application_text,
)

from substitute.domain.generation import (
    OutputResultPosition,
    canonical_output_source_key,
)
from substitute.domain.workflow import (
    ImageMeta,
    OutputFocusMode,
    WorkflowState,
)
from substitute.application.workflows.output_canvas_projection_model import (
    OutputCanvasImageItem,
    OutputCanvasProjection,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_canvas_route_projection import (
    resolve_output_canvas_route,
)


def build_output_canvas_projection(
    workflow: WorkflowState,
    image_meta_map: Mapping[UUID, ImageMeta],
) -> OutputCanvasProjection:
    """Return grouped output-canvas presentation state for a workflow."""

    projection_items = _projection_items(workflow, image_meta_map)
    preferred_image_id = _manually_selected_image_id(workflow, image_meta_map)
    sources, set_count, _items_by_uuid = _source_groups_for_items(
        projection_items,
        preferred_image_id=preferred_image_id,
    )
    scene_groups = _scene_groups_for_items(
        projection_items,
        preferred_image_id=preferred_image_id,
    )
    route = resolve_output_canvas_route(
        workflow,
        sources=sources,
        scene_groups=scene_groups,
        image_meta_map=image_meta_map,
    )

    projection = OutputCanvasProjection(
        sources=sources,
        active_source_key=route.active_source_key,
        active_set_index=route.active_set_index,
        active_uuid=route.active_uuid,
        set_count=set_count,
        scene_groups=scene_groups,
        active_scene_key=route.active_scene_key,
        active_scene_overview=route.active_scene_overview,
        scene_count=route.scene_count,
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
    *,
    preferred_image_id: UUID | None = None,
) -> tuple[
    tuple[OutputCanvasSourceGroup, ...],
    int,
    dict[UUID, tuple[str, OutputCanvasImageItem]],
]:
    """Return source groups, max set count, and image focus lookup for items."""

    grouped_items: OrderedDict[str, list[tuple[UUID, ImageMeta]]] = OrderedDict()
    source_labels: dict[str, str] = {}
    source_labels_are_default: dict[str, bool] = {}
    for image_id, image_meta in image_items:
        source_key = _source_key_for(image_id, image_meta)
        grouped_items.setdefault(source_key, []).append((image_id, image_meta))
        source_labels.setdefault(source_key, _source_label_for(image_meta))
        source_labels_are_default.setdefault(
            source_key,
            _source_label_is_default(image_meta),
        )

    sources: list[OutputCanvasSourceGroup] = []
    set_count = 0
    items_by_uuid: dict[UUID, tuple[str, OutputCanvasImageItem]] = {}

    source_entries = tuple(grouped_items.items())
    if source_entries and all(
        source_key.startswith("direct:") for source_key, _items in source_entries
    ):
        source_entries = tuple(
            sorted(
                source_entries,
                key=lambda entry: _direct_source_order(source_labels.get(entry[0], "")),
            )
        )

    for source_key, source_image_items in source_entries:
        images_by_set: dict[int, OutputCanvasImageItem] = {}
        fallback_index = 1
        positioned_items = tuple(
            (image_id, image_meta)
            for image_id, image_meta in source_image_items
            if image_meta.list_index is not None
        )
        uses_explicit_batch_coordinates = any(
            image_meta.batch_index is not None
            for _image_id, image_meta in positioned_items
        )
        ordered_positioned_items = (
            tuple(
                sorted(
                    _items_for_projected_positions(
                        positioned_items,
                        preferred_image_id=preferred_image_id,
                    ),
                    key=_position_sort_key,
                )
            )
            if uses_explicit_batch_coordinates
            else positioned_items
        )
        for ordinal, (image_id, image_meta) in enumerate(
            ordered_positioned_items,
            start=1,
        ):
            if image_meta.list_index is None:
                continue
            position = OutputResultPosition(
                list_index=image_meta.list_index,
                batch_index=image_meta.batch_index or 0,
            )
            set_index = (
                ordinal
                if uses_explicit_batch_coordinates
                else image_meta.list_index + 1
            )
            item = OutputCanvasImageItem(
                image_id=image_id,
                image_meta=image_meta,
                set_index=set_index,
                position=position,
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
                position=None,
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
                label_is_default=source_labels_are_default[source_key],
            )
        )

    return tuple(sources), set_count, items_by_uuid


def _position_sort_key(entry: tuple[UUID, ImageMeta]) -> tuple[int, int]:
    """Return a total order for metadata known to carry a list coordinate."""

    image_meta = entry[1]
    return image_meta.list_index or 0, image_meta.batch_index or 0


def _items_for_projected_positions(
    image_items: tuple[tuple[UUID, ImageMeta], ...],
    *,
    preferred_image_id: UUID | None,
) -> tuple[tuple[UUID, ImageMeta], ...]:
    """Keep one result per backend position while retaining manual focus."""

    latest_by_position: dict[tuple[int, int], tuple[UUID, ImageMeta]] = {}
    for image_id, image_meta in image_items:
        latest_by_position[
            (image_meta.list_index or 0, image_meta.batch_index or 0)
        ] = (image_id, image_meta)
    for image_id, image_meta in image_items:
        if image_id != preferred_image_id:
            continue
        latest_by_position[
            (image_meta.list_index or 0, image_meta.batch_index or 0)
        ] = (image_id, image_meta)
        break
    return tuple(latest_by_position.values())


def _direct_source_order(label: str) -> tuple[int, str]:
    """Return numeric manifest order for direct-workflow source labels."""

    try:
        return int(label), label
    except ValueError:
        return 2_147_483_647, label


def _scene_groups_for_items(
    image_items: tuple[tuple[UUID, ImageMeta], ...],
    *,
    preferred_image_id: UUID | None = None,
) -> tuple[OutputCanvasSceneGroup, ...]:
    """Return prompt-scene groups in scene order for output items."""

    grouped_items: OrderedDict[str, list[tuple[UUID, ImageMeta]]] = OrderedDict()
    scene_run_ids: dict[str, str] = {}
    scene_titles: dict[str, str] = {}
    scene_titles_are_default: dict[str, bool] = {}
    scene_orders: dict[str, int] = {}
    for image_id, image_meta in image_items:
        scene_key = _scene_key_for(image_meta)
        grouped_items.setdefault(scene_key, []).append((image_id, image_meta))
        scene_run_ids.setdefault(scene_key, image_meta.scene_run_id)
        scene_titles.setdefault(scene_key, _scene_title_for(image_meta))
        scene_titles_are_default.setdefault(
            scene_key,
            _scene_title_is_default(image_meta),
        )
        scene_orders.setdefault(scene_key, _scene_order_for(image_meta))

    groups: list[OutputCanvasSceneGroup] = []
    for scene_key, grouped_scene_items in grouped_items.items():
        sources, _set_count, _items_by_uuid = _source_groups_for_items(
            tuple(grouped_scene_items),
            preferred_image_id=preferred_image_id,
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
                title_is_default=scene_titles_are_default[scene_key],
            )
        )
    return tuple(sorted(groups, key=lambda group: (group.order, group.scene_key)))


def _manually_selected_image_id(
    workflow: WorkflowState,
    image_meta_map: Mapping[UUID, ImageMeta],
) -> UUID | None:
    """Return a valid concrete manual selection that projection must retain."""

    selected_image_id = workflow.active_output_uuid
    if (
        workflow.output_focus_mode is not OutputFocusMode.MANUAL
        or workflow.active_output_set_index <= 0
        or selected_image_id not in image_meta_map
    ):
        return None
    return selected_image_id


def _scene_representative_for_sources(
    sources: tuple[OutputCanvasSourceGroup, ...],
) -> tuple[str | None, int | None, UUID | None]:
    """Return the terminal scene source, set index, and representative image id."""

    for source in reversed(sources):
        item = source.first_item()
        if item is not None:
            return source.source_key, item.set_index, item.image_id
    return None, None, None


def _source_key_for(image_id: UUID, image_meta: ImageMeta) -> str:
    """Return stable grouping identity for one output image."""

    if image_meta.source_key:
        return canonical_output_source_key(
            source_key=image_meta.source_key,
            source_label=image_meta.source_label,
            node_id=image_meta.node_id,
        )
    if image_meta.cube_name:
        return image_meta.cube_name
    return str(image_id)


def _source_label_for(image_meta: ImageMeta) -> str:
    """Return display label for one output source group."""

    if image_meta.source_label:
        return image_meta.source_label
    if image_meta.cube_name:
        return image_meta.cube_name
    return render_source_application_text(app_text("Output"))


def _source_label_is_default(image_meta: ImageMeta) -> bool:
    """Return whether source presentation uses app-owned fallback copy."""

    return not image_meta.source_label and not image_meta.cube_name


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
    return render_source_application_text(app_text("Scene"))


def _scene_title_is_default(image_meta: ImageMeta) -> bool:
    """Return whether scene presentation uses app-owned fallback copy."""

    return not image_meta.scene_title


def output_source_label_text(source: OutputCanvasSourceGroup) -> ApplicationText:
    """Classify one source label as app fallback or exact authored content."""

    return app_text("Output") if source.label_is_default else opaque_text(source.label)


def output_scene_title_text(scene: OutputCanvasSceneGroup) -> ApplicationText:
    """Classify one scene title as app fallback or exact authored content."""

    return app_text("Scene") if scene.title_is_default else opaque_text(scene.title)


def _scene_order_for(image_meta: ImageMeta) -> int:
    """Return scene display order for one output image."""

    if image_meta.scene_order is not None:
        return image_meta.scene_order
    return 0


__all__ = [
    "OutputCanvasImageItem",
    "OutputCanvasProjection",
    "OutputCanvasSceneGroup",
    "OutputCanvasSourceGroup",
    "build_output_canvas_projection",
    "output_scene_title_text",
    "output_source_label_text",
]

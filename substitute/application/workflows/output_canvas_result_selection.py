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

"""Select one Output run and its independently queued result positions."""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from substitute.domain.workflow import ImageMeta, WorkflowState


def output_projection_items(
    workflow: WorkflowState,
    image_meta_map: Mapping[UUID, ImageMeta],
) -> tuple[tuple[UUID, ImageMeta], ...]:
    """Return only the latest explicit Output session in workflow display order."""

    items = tuple(
        (image_id, image_meta)
        for image_id in workflow.output_image_uuids
        if (image_meta := image_meta_map.get(image_id)) is not None
    )
    latest_session_id = next(
        (
            image_meta.output_session_id
            for _image_id, image_meta in reversed(items)
            if image_meta.output_session_id
        ),
        "",
    )
    if not latest_session_id:
        return items
    return tuple(
        item for item in items if item[1].output_session_id == latest_session_id
    )


def ordered_projected_position_items(
    image_items: tuple[tuple[UUID, ImageMeta], ...],
    *,
    preferred_image_id: UUID | None,
) -> tuple[tuple[UUID, ImageMeta], ...]:
    """Retain each job position within a run and legacy replacement semantics."""

    latest_by_position: dict[tuple[str, int, int], tuple[UUID, ImageMeta]] = {}
    for image_id, image_meta in image_items:
        latest_by_position[_position_key(image_meta)] = (image_id, image_meta)
    for image_id, image_meta in image_items:
        if image_id == preferred_image_id:
            latest_by_position[_position_key(image_meta)] = (image_id, image_meta)
            break
    selected = tuple(latest_by_position.values())
    if any(image_meta.output_session_id for _image_id, image_meta in image_items):
        run_order: dict[str, int] = {}
        for order, (_image_id, image_meta) in enumerate(image_items):
            run_order.setdefault(image_meta.generation_run_id, order)
        return tuple(
            sorted(
                selected,
                key=lambda entry: (
                    run_order[entry[1].generation_run_id],
                    entry[1].list_index or 0,
                    entry[1].batch_index or 0,
                ),
            )
        )
    return tuple(sorted(selected, key=_legacy_position_sort_key))


def _position_key(image_meta: ImageMeta) -> tuple[str, int, int]:
    """Return a position key that distinguishes jobs within one Output session."""

    return (
        image_meta.generation_run_id if image_meta.output_session_id else "",
        image_meta.list_index or 0,
        image_meta.batch_index or 0,
    )


def _legacy_position_sort_key(entry: tuple[UUID, ImageMeta]) -> tuple[int, int]:
    """Return the historical total order for legacy backend coordinates."""

    image_meta = entry[1]
    return image_meta.list_index or 0, image_meta.batch_index or 0


__all__ = ["ordered_projected_position_items", "output_projection_items"]

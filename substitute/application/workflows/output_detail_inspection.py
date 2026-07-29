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

"""Derive Output detail-inspection peers from product projection semantics."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid5

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
    OutputCanvasSourceGroup,
)

_OUTPUT_DETAIL_GROUP_NAMESPACE = UUID("b91d84ce-9596-4c04-807a-6f3eb0af2539")
_UNSCENED_KEY = "unscened"


@dataclass(frozen=True, slots=True)
class OutputDetailInspectionGroup:
    """Describe corresponding Cube outputs for one workflow scene and batch."""

    group_id: UUID
    workflow_id: str
    scene_key: str
    set_index: int
    image_ids: tuple[UUID, ...]


def output_detail_inspection_groups(
    *,
    workflow_id: str,
    projection: OutputCanvasProjection,
) -> tuple[OutputDetailInspectionGroup, ...]:
    """Return link groups scoped to exact workflow, scene, and batch peers."""

    if not workflow_id:
        raise ValueError("workflow_id must not be empty")
    scopes = (
        tuple((scene.scene_key, scene.sources) for scene in projection.scene_groups)
        if projection.scene_groups
        else ((_UNSCENED_KEY, projection.sources),)
    )
    groups: list[OutputDetailInspectionGroup] = []
    for scene_key, sources in scopes:
        for set_index in _set_indices(sources):
            image_ids = tuple(
                item.image_id
                for source in sources
                if (item := source.images_by_set.get(set_index)) is not None
            )
            image_ids = tuple(dict.fromkeys(image_ids))
            if len(image_ids) < 2:
                continue
            groups.append(
                OutputDetailInspectionGroup(
                    group_id=_detail_group_id(
                        workflow_id=workflow_id,
                        scene_key=scene_key,
                        set_index=set_index,
                    ),
                    workflow_id=workflow_id,
                    scene_key=scene_key,
                    set_index=set_index,
                    image_ids=image_ids,
                )
            )
    return tuple(groups)


def _set_indices(sources: tuple[OutputCanvasSourceGroup, ...]) -> tuple[int, ...]:
    """Return every concrete batch index in stable display order."""

    return tuple(
        sorted(
            {
                set_index
                for source in sources
                for set_index in source.images_by_set
                if set_index > 0
            }
        )
    )


def _detail_group_id(*, workflow_id: str, scene_key: str, set_index: int) -> UUID:
    """Return a stable identity for one product-owned inspection scope."""

    return uuid5(
        _OUTPUT_DETAIL_GROUP_NAMESPACE,
        f"workflow:{workflow_id};scene:{scene_key};set:{set_index}",
    )


__all__ = ["OutputDetailInspectionGroup", "output_detail_inspection_groups"]

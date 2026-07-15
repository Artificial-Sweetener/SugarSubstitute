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

"""Resolve Output canvas route identities and authorized display scopes."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

from substitute.application.workflows.output_canvas_session import (
    OutputCanvasSession,
    deterministic_host_composition_id,
    output_route_identity_for_projection,
)
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
)
from substitute.application.workflows.output_preview_registry import OutputPreviewLane
from substitute.domain.workflow import CanvasKind, CanvasRouteIdentity


@dataclass(frozen=True, slots=True)
class OutputRouteScopeMembers:
    """Describe Output route members authorized for one display scope."""

    image_ids: frozenset[UUID]
    source_keys: frozenset[str]
    scene_keys: frozenset[str]
    composition_ids: frozenset[UUID]


def route_source_and_scene(
    route: CanvasRouteIdentity,
) -> tuple[str | None, str | None]:
    """Return source and scene identities encoded in one route key."""

    source_key: str | None = None
    scene_key: str | None = None
    for segment in route.route_key.split(";"):
        if segment.startswith("source:"):
            source_key = segment.removeprefix("source:")
        elif segment.startswith("scene:"):
            scene_key = segment.removeprefix("scene:")
    return source_key, scene_key


def route_targets_preview_lane(
    route: CanvasRouteIdentity,
    preview_lanes: Iterable[OutputPreviewLane],
) -> bool:
    """Return whether the route targets an accepted preview lane."""

    image_id = route.primary_image_id
    if image_id is None:
        return False
    return any(lane.preview_id == image_id for lane in preview_lanes)


def output_route_scope_members(
    *,
    session: OutputCanvasSession,
    route: CanvasRouteIdentity,
    preview_lanes: Iterable[OutputPreviewLane],
    active_scene_overview: bool,
    active_scene_key: str | None,
) -> OutputRouteScopeMembers:
    """Return session-owned route scope plus accepted transient previews."""

    preview_lanes_tuple = tuple(preview_lanes)
    image_ids = set(session.allowed_image_ids)
    image_ids.update(lane.preview_id for lane in preview_lanes_tuple)
    source_keys = set(session.allowed_source_keys)
    source_keys.update(lane.key.source_key for lane in preview_lanes_tuple)
    scene_keys = set(session.allowed_scene_keys)
    scene_keys.update(
        lane.key.scene_key
        for lane in preview_lanes_tuple
        if lane.key.scene_key is not None
    )
    if active_scene_overview and active_scene_key:
        scene_keys.add(active_scene_key)
    composition_ids = set(session.allowed_composition_ids)
    route_source_key, route_scene_key = route_source_and_scene(route)
    route_source_allowed = route_source_key is None or route_source_key in source_keys
    route_scene_allowed = (
        route_scene_key is None or not route_scene_key or route_scene_key in scene_keys
    )
    if (
        route.route_kind in {"source_grid", "scene_overview"}
        and route_source_allowed
        and route_scene_allowed
    ):
        composition_ids.add(
            deterministic_host_composition_id(
                canvas_kind=CanvasKind.OUTPUT,
                workflow_id=session.workflow_id.value,
                route=route,
            )
        )
    return OutputRouteScopeMembers(
        image_ids=frozenset(image_ids),
        source_keys=frozenset(source_keys),
        scene_keys=frozenset(scene_keys),
        composition_ids=frozenset(composition_ids),
    )


def output_route_identity_for_projection_scope(
    projection: OutputCanvasProjection,
) -> CanvasRouteIdentity:
    """Return the route identity represented by one Output projection."""

    return output_route_identity_for_projection(projection)


def source_grid_route_identity(
    *,
    source_key: str,
    active_scene_key: str | None,
) -> CanvasRouteIdentity:
    """Return the route identity for one source grid."""

    scene_key = active_scene_key or ""
    return CanvasRouteIdentity(
        route_kind="source_grid",
        route_key=f"scene:{scene_key};source:{source_key};set:0",
    )


def scene_overview_route_identity(
    *,
    active_scene_key: str | None,
) -> CanvasRouteIdentity:
    """Return the route identity for one scene overview."""

    scene_key = active_scene_key or ""
    return CanvasRouteIdentity(
        route_kind="scene_overview",
        route_key=f"scene:{scene_key}",
    )


__all__ = [
    "OutputRouteScopeMembers",
    "output_route_identity_for_projection_scope",
    "output_route_scope_members",
    "route_source_and_scene",
    "route_targets_preview_lane",
    "scene_overview_route_identity",
    "source_grid_route_identity",
]

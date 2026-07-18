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

"""Build typed Output canvas projection sessions without applying display routes."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid5

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
)
from substitute.domain.workflow import (
    CanvasGenerationIdentity,
    CanvasKind,
    CanvasRouteIdentity,
    CanvasSessionRevision,
    CanvasSessionToken,
    CanvasWorkflowIdentity,
    ImageMeta,
    OutputCanvasSession as OutputCanvasRouteSession,
)

_HOST_ROUTE_COMPOSITION_NAMESPACE = UUID("1d901bd3-81ad-4c52-b8ed-f7556acbcfb0")


class OutputCanvasSessionBoundary(Protocol):
    """Bind shared Output route sessions for typed projection authority."""

    def bind_output_session(
        self,
        *,
        workflow_id: str,
        active_route: CanvasRouteIdentity,
        generation_identity: CanvasGenerationIdentity | None = None,
    ) -> OutputCanvasRouteSession:
        """Bind the shared Output route session and return its identity."""


@dataclass(frozen=True, slots=True)
class OutputCanvasSession:
    """Bind one Output projection to one shared session revision."""

    session: OutputCanvasRouteSession
    projection: OutputCanvasProjection
    allowed_image_ids: frozenset[UUID]
    allowed_source_keys: frozenset[str]
    allowed_scene_keys: frozenset[str]
    allowed_composition_ids: frozenset[UUID]

    def __post_init__(self) -> None:
        """Reject non-Output shared sessions and mismatched route authority."""

        if self.session.canvas_kind is not CanvasKind.OUTPUT:
            raise ValueError("Output canvas sessions must use CanvasKind.OUTPUT.")
        if self.session.active_route != output_route_identity_for_projection(
            self.projection
        ):
            raise ValueError("Output canvas session route must match its projection.")

    @property
    def workflow_id(self) -> CanvasWorkflowIdentity:
        """Return the workflow identity bound to this projection session."""

        return self.session.workflow_id

    @property
    def canvas_kind(self) -> CanvasKind:
        """Return the canvas kind bound to this projection session."""

        return self.session.canvas_kind

    @property
    def revision(self) -> CanvasSessionRevision:
        """Return the session revision that makes this projection current."""

        return self.session.revision

    @property
    def projection_revision(self) -> CanvasSessionRevision:
        """Return the revision bound to this Output projection."""

        return self.session.revision

    @property
    def active_route(self) -> CanvasRouteIdentity:
        """Return the active route represented by this projection."""

        return self.session.active_route

    @property
    def generation_identity(self) -> CanvasGenerationIdentity | None:
        """Return generation identity for the active concrete image, if any."""

        return self.session.generation_identity

    def token(self) -> CanvasSessionToken:
        """Return a stale-check token for later display mutation attempts."""

        return self.session.token()


def bind_output_canvas_session(
    session_boundary: OutputCanvasSessionBoundary,
    *,
    workflow_id: str,
    projection: OutputCanvasProjection,
    image_metadata_lookup: Mapping[UUID, ImageMeta],
) -> OutputCanvasSession:
    """Bind and return authoritative Output session state for one projection."""

    active_route = output_route_identity_for_projection(projection)
    route_session = session_boundary.bind_output_session(
        workflow_id=workflow_id,
        active_route=active_route,
        generation_identity=_output_generation_identity(
            projection,
            image_metadata_lookup,
        ),
    )
    return OutputCanvasSession(
        session=route_session,
        projection=projection,
        allowed_image_ids=allowed_output_image_ids(projection),
        allowed_source_keys=allowed_output_source_keys(projection),
        allowed_scene_keys=allowed_output_scene_keys(projection),
        allowed_composition_ids=allowed_output_composition_ids(
            workflow_id=workflow_id,
            projection=projection,
        ),
    )


def output_route_identity_for_projection(
    projection: OutputCanvasProjection,
) -> CanvasRouteIdentity:
    """Return the active Output route identity represented by a projection."""

    scene_key = projection.active_scene_key or ""
    if projection.active_scene_overview:
        return CanvasRouteIdentity(
            route_kind="scene_overview",
            route_key=f"scene:{scene_key}",
        )
    if projection.active_uuid is not None:
        source_key = projection.active_source_key or ""
        return CanvasRouteIdentity(
            route_kind="output_image",
            route_key=(
                f"image:{projection.active_uuid};scene:{scene_key};"
                f"source:{source_key};set:{projection.active_set_index}"
            ),
            primary_image_id=projection.active_uuid,
        )
    if projection.active_source_key is not None and projection.active_set_index == 0:
        return CanvasRouteIdentity(
            route_kind="source_grid",
            route_key=f"scene:{scene_key};source:{projection.active_source_key};set:0",
        )
    return CanvasRouteIdentity.empty()


def allowed_output_image_ids(projection: OutputCanvasProjection) -> frozenset[UUID]:
    """Return every image ID the projection can later authorize."""

    image_ids: set[UUID] = set()
    for source in projection.sources:
        image_ids.update(item.image_id for item in source.images_by_set.values())
    for scene in projection.scene_groups:
        if scene.preview_image_id is not None:
            image_ids.add(scene.preview_image_id)
        if scene.primary_image_id is not None:
            image_ids.add(scene.primary_image_id)
        for source in scene.sources:
            image_ids.update(item.image_id for item in source.images_by_set.values())
    return frozenset(image_ids)


def allowed_output_source_keys(
    projection: OutputCanvasProjection,
) -> frozenset[str]:
    """Return every stable source key the projection can later authorize."""

    source_keys = {source.source_key for source in projection.sources}
    for scene in projection.scene_groups:
        source_keys.update(source.source_key for source in scene.sources)
    return frozenset(source_keys)


def allowed_output_scene_keys(
    projection: OutputCanvasProjection,
) -> frozenset[str]:
    """Return every stable scene key the projection can later authorize."""

    return frozenset(scene.scene_key for scene in projection.scene_groups)


def allowed_output_composition_ids(
    *,
    workflow_id: str,
    projection: OutputCanvasProjection,
) -> frozenset[UUID]:
    """Return stable host composition IDs addressable by this projection."""

    routes: set[CanvasRouteIdentity] = set()
    active_route = output_route_identity_for_projection(projection)
    if active_route.route_kind == "source_grid":
        routes.add(active_route)
    scene_key = projection.active_scene_key or ""
    if projection.scene_count > 1:
        routes.add(
            CanvasRouteIdentity(
                route_kind="scene_overview", route_key=f"scene:{scene_key}"
            )
        )
    for source in projection.sources:
        if len(source.images_by_set) > 1:
            routes.add(
                CanvasRouteIdentity(
                    route_kind="source_grid",
                    route_key=f"scene:{scene_key};source:{source.source_key};set:0",
                )
            )
    for scene in projection.scene_groups:
        for source in scene.sources:
            if len(source.images_by_set) > 1:
                routes.add(
                    CanvasRouteIdentity(
                        route_kind="source_grid",
                        route_key=(
                            f"scene:{scene.scene_key};source:{source.source_key};set:0"
                        ),
                    )
                )
    return frozenset(
        deterministic_host_composition_id(
            canvas_kind=CanvasKind.OUTPUT,
            workflow_id=workflow_id,
            route=route,
        )
        for route in routes
    )


def deterministic_host_composition_id(
    *,
    canvas_kind: CanvasKind,
    workflow_id: str,
    route: CanvasRouteIdentity,
) -> UUID:
    """Return the stable host-owned composition ID for one route."""

    return uuid5(
        _HOST_ROUTE_COMPOSITION_NAMESPACE,
        (
            f"canvas:{canvas_kind.value};workflow:{workflow_id};"
            f"route:{route.route_kind};key:{route.route_key}"
        ),
    )


def _output_generation_identity(
    projection: OutputCanvasProjection,
    image_metadata_lookup: Mapping[UUID, ImageMeta],
) -> CanvasGenerationIdentity | None:
    """Return complete generation identity for the active concrete image."""

    if projection.active_uuid is None:
        return None
    image_meta = image_metadata_lookup.get(projection.active_uuid)
    if image_meta is None:
        return None
    generation_run_id = str(getattr(image_meta, "generation_run_id", "") or "")
    prompt_id = str(getattr(image_meta, "prompt_id", "") or "")
    client_id = str(getattr(image_meta, "client_id", "") or "")
    if not (generation_run_id and prompt_id and client_id):
        return None
    return CanvasGenerationIdentity(
        generation_run_id=generation_run_id,
        prompt_id=prompt_id,
        client_id=client_id,
    )


__all__ = [
    "OutputCanvasSession",
    "OutputCanvasSessionBoundary",
    "allowed_output_composition_ids",
    "allowed_output_image_ids",
    "allowed_output_scene_keys",
    "allowed_output_source_keys",
    "bind_output_canvas_session",
    "deterministic_host_composition_id",
    "output_route_identity_for_projection",
]

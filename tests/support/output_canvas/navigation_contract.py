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

"""Build explicit Output fixtures and assert cross-layer navigation contracts."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid5

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
    OutputCanvasSourceGroup,
    build_output_canvas_projection,
)
from substitute.application.workflows.output_canvas_session import (
    bind_output_canvas_session,
    deterministic_host_composition_id,
    output_route_identity_for_projection,
)
from substitute.domain.workflow import (
    CanvasKind,
    CanvasRouteIdentity,
    CanvasSessionBoundary,
    ImageMeta,
    WorkflowState,
)
from substitute.presentation.canvas.output.output_canvas_route_model import (
    OutputCanvasRouteCommand,
    OutputCanvasRouteModel,
)

_FIXTURE_NAMESPACE = UUID("8a658e94-511d-4e93-af3e-f6a6e167be83")


@dataclass(frozen=True, slots=True)
class OutputSourceSpec:
    """Describe one fixture source and its concrete batch count."""

    key: str
    label: str
    batch_count: int


@dataclass(slots=True)
class OutputNavigationFixture:
    """Carry authored workflow state, metadata, and stable coordinate identities."""

    workflow_id: str
    workflow: WorkflowState
    metadata_by_id: dict[UUID, ImageMeta]
    image_id_by_coordinate: dict[tuple[str, str, int], UUID]

    def image_id(self, scene_key: str, source_key: str, set_index: int) -> UUID:
        """Return the stable image identity for one fixture coordinate."""

        return self.image_id_by_coordinate[(scene_key, source_key, set_index)]

    def project(self) -> OutputCanvasProjection:
        """Build a production projection from current durable workflow state."""

        return build_output_canvas_projection(self.workflow, self.metadata_by_id)


@dataclass(frozen=True, slots=True)
class OutputNavigationContract:
    """Expose cross-layer route facts established by one invariant audit."""

    projection: OutputCanvasProjection
    route_command: OutputCanvasRouteCommand
    route_identity: CanvasRouteIdentity
    visible_sources: tuple[OutputCanvasSourceGroup, ...]
    visible_image_ids: frozenset[UUID]


def build_navigation_fixture(
    *,
    workflow_id: str = "workflow",
    scene_keys: tuple[str, ...] = (),
    sources: tuple[OutputSourceSpec, ...] = (OutputSourceSpec("text", "Text", 1),),
) -> OutputNavigationFixture:
    """Return deterministic output state for explicit navigation contract cases."""

    workflow = WorkflowState(metadata={"name": workflow_id})
    metadata_by_id: dict[UUID, ImageMeta] = {}
    image_id_by_coordinate: dict[tuple[str, str, int], UUID] = {}
    scene_coordinates: tuple[str | None, ...] = scene_keys or (None,)
    for scene_order, scene_key in enumerate(scene_coordinates):
        for source in sources:
            for batch_index in range(source.batch_count):
                coordinate_scene_key = scene_key or ""
                set_index = batch_index + 1
                image_id = uuid5(
                    _FIXTURE_NAMESPACE,
                    (f"{workflow_id}:{coordinate_scene_key}:{source.key}:{set_index}"),
                )
                image_id_by_coordinate[
                    (coordinate_scene_key, source.key, set_index)
                ] = image_id
                metadata_by_id[image_id] = ImageMeta(
                    workflow_name=workflow_id,
                    cube_name=source.label,
                    image_number=set_index,
                    suffix="",
                    path=f"{workflow_id}/{image_id}.png",
                    source_key=source.key,
                    source_label=source.label,
                    scene_run_id=f"run:{workflow_id}" if scene_key else "",
                    scene_key=coordinate_scene_key,
                    scene_title=(scene_key or ""),
                    scene_order=scene_order if scene_key else None,
                    scene_count=len(scene_keys) if scene_keys else None,
                    list_index=0,
                    batch_index=batch_index,
                )
                workflow.output_image_uuids.append(image_id)
    return OutputNavigationFixture(
        workflow_id=workflow_id,
        workflow=workflow,
        metadata_by_id=metadata_by_id,
        image_id_by_coordinate=image_id_by_coordinate,
    )


def assert_output_navigation_contract(
    fixture: OutputNavigationFixture,
) -> OutputNavigationContract:
    """Assert canonical route agreement across projection, model, and session."""

    projection = fixture.project()
    assert projection == fixture.project(), "unchanged projection must be idempotent"
    scene_groups = OutputCanvasRouteModel.scene_groups_by_key(
        projection,
        preview_scene_groups_by_key={},
    )
    visible_sources_by_key = OutputCanvasRouteModel.visible_source_groups_by_key(
        projection,
        scene_groups_by_key=scene_groups,
        active_scene_overview=projection.active_scene_overview,
        active_scene_key=projection.active_scene_key,
        scene_count=projection.scene_count,
    )
    route_command = OutputCanvasRouteModel.route_command_for_selection(
        active_scene_overview=projection.active_scene_overview,
        scene_count=projection.scene_count,
        active_set_index=projection.active_set_index,
        active_source_key=projection.active_source_key,
        active_scene_key=projection.active_scene_key,
        active_image_id=projection.active_uuid,
    )
    route_identity = output_route_identity_for_projection(projection)
    session = bind_output_canvas_session(
        CanvasSessionBoundary(),
        workflow_id=fixture.workflow_id,
        projection=projection,
        image_metadata_lookup=fixture.metadata_by_id,
    )
    workflow_image_ids = frozenset(fixture.workflow.output_image_uuids)
    visible_image_ids = frozenset(
        item.image_id
        for source in visible_sources_by_key.values()
        for item in source.images_by_set.values()
    )

    assert session.active_route == route_identity
    assert session.allowed_image_ids <= workflow_image_ids
    assert visible_image_ids <= workflow_image_ids
    assert session.allowed_source_keys == frozenset(
        source.source_key for source in projection.sources
    ) | frozenset(
        source.source_key
        for scene in projection.scene_groups
        for source in scene.sources
    )
    assert session.allowed_scene_keys == frozenset(scene_groups)

    if projection.active_scene_overview:
        assert projection.scene_count > 1
        assert projection.active_source_key is None
        assert projection.active_set_index == 1
        assert projection.active_uuid is None
        assert visible_sources_by_key == {}
        assert route_command.kind == "scene_overview"
        assert route_identity.route_kind == "scene_overview"
    elif projection.active_set_index == 0:
        assert projection.active_source_key in visible_sources_by_key
        assert projection.active_uuid is None
        assert route_command.kind == "source_grid"
        assert route_identity.route_kind == "source_grid"
        source = visible_sources_by_key[projection.active_source_key]
        assert visible_image_ids >= frozenset(
            item.image_id for item in source.images_by_set.values()
        )
        composition_id = deterministic_host_composition_id(
            canvas_kind=CanvasKind.OUTPUT,
            workflow_id=fixture.workflow_id,
            route=route_identity,
        )
        assert composition_id in session.allowed_composition_ids
    elif projection.active_uuid is not None:
        assert projection.active_set_index > 0
        assert projection.active_source_key in visible_sources_by_key
        source = visible_sources_by_key[projection.active_source_key]
        item = source.images_by_set.get(projection.active_set_index)
        assert item is not None
        assert item.image_id == projection.active_uuid
        assert projection.active_uuid in session.allowed_image_ids
        assert route_command.kind == "image"
        assert route_identity.route_kind == "output_image"
        assert route_identity.primary_image_id == projection.active_uuid
    else:
        assert not projection.sources
        assert route_command.kind == "empty"
        assert route_identity.route_kind == "empty"

    return OutputNavigationContract(
        projection=projection,
        route_command=route_command,
        route_identity=route_identity,
        visible_sources=tuple(visible_sources_by_key.values()),
        visible_image_ids=visible_image_ids,
    )


__all__ = [
    "OutputNavigationContract",
    "OutputNavigationFixture",
    "OutputSourceSpec",
    "assert_output_navigation_contract",
    "build_navigation_fixture",
]

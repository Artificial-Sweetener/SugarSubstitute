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

"""Verify pure Output canvas route-scope resolution."""

from __future__ import annotations

from uuid import UUID, uuid4

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasProjection,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_canvas_route_scope import (
    output_route_identity_for_projection_scope,
    output_route_scope_members,
    route_source_and_scene,
    route_targets_preview_lane,
    scene_overview_route_identity,
    source_grid_route_identity,
)
from substitute.application.workflows.output_canvas_session import (
    OutputCanvasSession,
    bind_output_canvas_session,
    deterministic_host_composition_id,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewLane,
    OutputPreviewLaneKey,
)
from substitute.domain.workflow import (
    CanvasKind,
    CanvasRouteIdentity,
    CanvasSessionBoundary,
    CanvasSessionRevision,
    ImageMeta,
)


def test_route_source_and_scene_extracts_key_segments() -> None:
    """Route-key parsing should ignore unrelated route segments."""

    route = CanvasRouteIdentity(
        route_kind="source_grid",
        route_key="scene:scene-a;source:source-a;set:0",
    )

    assert route_source_and_scene(route) == ("source-a", "scene-a")


def test_source_grid_and_scene_overview_route_identity_include_scene_context() -> None:
    """Grid routes should preserve active scene context for authorization."""

    assert source_grid_route_identity(
        source_key="source-a",
        active_scene_key="scene-a",
    ) == CanvasRouteIdentity(
        route_kind="source_grid",
        route_key="scene:scene-a;source:source-a;set:0",
    )
    assert scene_overview_route_identity(
        active_scene_key="scene-a"
    ) == CanvasRouteIdentity(
        route_kind="scene_overview",
        route_key="scene:scene-a",
    )


def test_route_scope_members_include_preview_lane_and_host_composition() -> None:
    """Route scope should include accepted previews and authorized host grids."""

    image_id = uuid4()
    preview_id = uuid4()
    session = _session(
        workflow_id="workflow-a",
        image_id=image_id,
        source_key="source-a",
        scene_key="scene-a",
    )
    route = source_grid_route_identity(
        source_key="source-a",
        active_scene_key="scene-a",
    )
    preview_lane = _preview_lane(
        preview_id=preview_id,
        workflow_id="workflow-a",
        source_key="source-b",
        scene_key="scene-b",
        session_revision=session.revision,
    )

    members = output_route_scope_members(
        session=session,
        route=route,
        preview_lanes=(preview_lane,),
        active_scene_overview=True,
        active_scene_key="scene-a",
    )

    assert members.image_ids == frozenset({image_id, preview_id})
    assert members.source_keys == frozenset({"source-a", "source-b"})
    assert members.scene_keys == frozenset({"scene-a", "scene-b"})
    assert (
        deterministic_host_composition_id(
            canvas_kind=CanvasKind.OUTPUT,
            workflow_id="workflow-a",
            route=route,
        )
        in members.composition_ids
    )


def test_route_scope_members_reject_foreign_host_composition() -> None:
    """Host composition ids should not be authorized for foreign route keys."""

    session = _session(
        workflow_id="workflow-a",
        image_id=uuid4(),
        source_key="source-a",
        scene_key="scene-a",
    )
    foreign_route = source_grid_route_identity(
        source_key="source-x",
        active_scene_key="scene-a",
    )

    members = output_route_scope_members(
        session=session,
        route=foreign_route,
        preview_lanes=(),
        active_scene_overview=False,
        active_scene_key=None,
    )

    assert (
        deterministic_host_composition_id(
            canvas_kind=CanvasKind.OUTPUT,
            workflow_id="workflow-a",
            route=foreign_route,
        )
        not in members.composition_ids
    )


def test_route_targets_preview_lane_checks_primary_image_id() -> None:
    """Only primary-image routes that match accepted previews target previews."""

    preview_id = uuid4()
    preview_lane = _preview_lane(
        preview_id=preview_id,
        workflow_id="workflow-a",
        source_key="source-a",
        scene_key=None,
        session_revision=CanvasSessionRevision(1),
    )

    assert route_targets_preview_lane(
        CanvasRouteIdentity(
            route_kind="output_image",
            route_key=f"image:{preview_id}",
            primary_image_id=preview_id,
        ),
        (preview_lane,),
    )
    assert not route_targets_preview_lane(CanvasRouteIdentity.empty(), (preview_lane,))


def test_projection_scope_route_identity_delegates_projection_rules() -> None:
    """Projection route identity should stay aligned with Output session binding."""

    image_id = uuid4()
    projection = _projection(
        image_id=image_id,
        source_key="source-a",
        scene_key="scene-a",
    )

    assert output_route_identity_for_projection_scope(projection) == (
        CanvasRouteIdentity(
            route_kind="output_image",
            route_key=f"image:{image_id};scene:scene-a;source:source-a;set:1",
            primary_image_id=image_id,
        )
    )


def _session(
    *,
    workflow_id: str,
    image_id: UUID,
    source_key: str,
    scene_key: str,
) -> OutputCanvasSession:
    """Return one bound Output projection session."""

    projection = _projection(
        image_id=image_id,
        source_key=source_key,
        scene_key=scene_key,
    )
    return bind_output_canvas_session(
        CanvasSessionBoundary(),
        workflow_id=workflow_id,
        projection=projection,
        image_metadata_lookup={
            image_id: _meta(source_key=source_key, scene_key=scene_key),
        },
    )


def _projection(
    *,
    image_id: UUID,
    source_key: str,
    scene_key: str,
) -> OutputCanvasProjection:
    """Return one source-backed Output projection."""

    image_item = OutputCanvasImageItem(
        image_id=image_id,
        image_meta=_meta(source_key=source_key, scene_key=scene_key),
        set_index=1,
    )
    return OutputCanvasProjection(
        sources=(
            OutputCanvasSourceGroup(
                source_key=source_key,
                label="Source",
                images_by_set={1: image_item},
            ),
        ),
        active_source_key=source_key,
        active_set_index=1,
        active_uuid=image_id,
        set_count=1,
        active_scene_key=scene_key,
    )


def _meta(*, source_key: str, scene_key: str) -> ImageMeta:
    """Return minimal output metadata for route-scope tests."""

    return ImageMeta(
        workflow_name="Workflow",
        cube_name="Output",
        image_number=1,
        suffix="",
        path="E:/out.png",
        source_key=source_key,
        source_label="Output",
        scene_key=scene_key,
    )


def _preview_lane(
    *,
    preview_id: UUID,
    workflow_id: str,
    source_key: str,
    scene_key: str | None,
    session_revision: CanvasSessionRevision,
) -> OutputPreviewLane:
    """Return one accepted Output preview lane."""

    return OutputPreviewLane(
        key=OutputPreviewLaneKey.source(
            workflow_id=workflow_id,
            generation_run_id="run-a",
            prompt_id="prompt-a",
            source_key=source_key,
            scene_key=scene_key,
        ),
        preview_id=preview_id,
        image=object(),
        source_label="Source",
        client_id="client-a",
        session_revision=session_revision,
    )

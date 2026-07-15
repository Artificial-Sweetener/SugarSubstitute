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

"""Contract tests for Output projection session authority construction."""

from __future__ import annotations

from uuid import uuid4

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasProjection,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.canvas_route_projector_port import (
    OutputRouteScope,
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
    CanvasSessionRejectionReason,
    ImageMeta,
)


def _meta(
    *,
    source_key: str = "source-a",
    generation_run_id: str = "",
    prompt_id: str = "",
    client_id: str = "",
) -> ImageMeta:
    """Return minimal output metadata for session tests."""

    return ImageMeta(
        workflow_name="Workflow",
        cube_name="Output",
        image_number=1,
        suffix="",
        path="E:/out.png",
        source_key=source_key,
        source_label="Output",
        generation_run_id=generation_run_id,
        prompt_id=prompt_id,
        client_id=client_id,
    )


def test_output_canvas_session_binds_projection_authority() -> None:
    """Output sessions should expose image, source, scene, and route authority."""

    image_id = uuid4()
    other_id = uuid4()
    image_meta = _meta(
        source_key="source-a",
        generation_run_id="run-1",
        prompt_id="prompt-1",
        client_id="client-1",
    )
    other_meta = _meta(source_key="source-b")
    source = OutputCanvasSourceGroup(
        source_key="source-a",
        label="Output",
        images_by_set={1: OutputCanvasImageItem(image_id, image_meta, 1)},
    )
    scene_source = OutputCanvasSourceGroup(
        source_key="source-b",
        label="Output",
        images_by_set={1: OutputCanvasImageItem(other_id, other_meta, 1)},
    )
    projection = OutputCanvasProjection(
        sources=(source,),
        active_source_key="source-a",
        active_set_index=1,
        active_uuid=image_id,
        set_count=1,
        scene_groups=(
            OutputCanvasSceneGroup(
                scene_run_id="scene-run",
                scene_key="scene-a",
                title="Scene A",
                order=0,
                sources=(scene_source,),
                primary_image_id=other_id,
                representative_source_key="source-b",
                representative_set_index=1,
            ),
        ),
        active_scene_key="scene-a",
        scene_count=1,
    )
    boundary = CanvasSessionBoundary()

    session = bind_output_canvas_session(
        boundary,
        workflow_id="wf",
        projection=projection,
        image_metadata_lookup={image_id: image_meta, other_id: other_meta},
    )

    assert session.session.workflow_id.value == "wf"
    assert session.session.canvas_kind is CanvasKind.OUTPUT
    assert session.projection_revision == session.session.revision
    assert session.projection is projection
    assert session.active_route == output_route_identity_for_projection(projection)
    assert session.active_route.primary_image_id == image_id
    assert session.allowed_image_ids == frozenset({image_id, other_id})
    assert session.allowed_source_keys == frozenset({"source-a", "source-b"})
    assert session.allowed_scene_keys == frozenset({"scene-a"})
    assert session.generation_identity is not None
    assert session.generation_identity.generation_run_id == "run-1"
    assert boundary.current_session(CanvasKind.OUTPUT) == session.session


def test_output_canvas_session_computes_deterministic_grid_composition_ids() -> None:
    """Source-grid sessions should expose deterministic composition IDs."""

    first_id = uuid4()
    second_id = uuid4()
    first_meta = _meta(source_key="source-a")
    second_meta = _meta(source_key="source-a")
    projection = OutputCanvasProjection(
        sources=(
            OutputCanvasSourceGroup(
                source_key="source-a",
                label="Output",
                images_by_set={
                    1: OutputCanvasImageItem(first_id, first_meta, 1),
                    2: OutputCanvasImageItem(second_id, second_meta, 2),
                },
            ),
        ),
        active_source_key="source-a",
        active_set_index=0,
        active_uuid=None,
        set_count=2,
    )

    session = bind_output_canvas_session(
        CanvasSessionBoundary(),
        workflow_id="wf",
        projection=projection,
        image_metadata_lookup={first_id: first_meta, second_id: second_meta},
    )
    route = CanvasRouteIdentity(
        route_kind="source_grid",
        route_key="scene:;source:source-a;set:0",
    )
    expected_id = deterministic_host_composition_id(
        canvas_kind=CanvasKind.OUTPUT,
        workflow_id="wf",
        route=route,
    )

    assert session.allowed_composition_ids == frozenset({expected_id})
    scope = OutputRouteScope(
        session=session,
        allowed_image_ids=session.allowed_image_ids,
        allowed_source_keys=session.allowed_source_keys,
        allowed_scene_keys=session.allowed_scene_keys,
        allowed_composition_ids=session.allowed_composition_ids,
    )

    assert scope.allowed_composition_ids == frozenset({expected_id})


def test_output_canvas_session_rebind_rejects_stale_projection_token() -> None:
    """A previous Output projection session should not authorize after rebind."""

    image_id = uuid4()
    image_meta = _meta(source_key="source-a")
    projection = OutputCanvasProjection(
        sources=(
            OutputCanvasSourceGroup(
                source_key="source-a",
                label="Output",
                images_by_set={1: OutputCanvasImageItem(image_id, image_meta, 1)},
            ),
        ),
        active_source_key="source-a",
        active_set_index=1,
        active_uuid=image_id,
        set_count=1,
    )
    boundary = CanvasSessionBoundary()
    stale_session = bind_output_canvas_session(
        boundary,
        workflow_id="wf",
        projection=projection,
        image_metadata_lookup={image_id: image_meta},
    )
    bind_output_canvas_session(
        boundary,
        workflow_id="wf",
        projection=projection,
        image_metadata_lookup={image_id: image_meta},
    )

    authorization = boundary.authorize_display_mutation(stale_session.token())

    assert authorization.accepted is False
    assert authorization.rejection_reason is CanvasSessionRejectionReason.STALE_REVISION

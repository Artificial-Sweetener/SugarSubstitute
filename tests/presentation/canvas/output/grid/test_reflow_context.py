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

"""Verify authoritative Output grid reflow context resolution."""

from __future__ import annotations

from uuid import uuid4

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasProjection,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_canvas_session import (
    OutputCanvasSession,
    bind_output_canvas_session,
)
from substitute.domain.workflow import CanvasSessionBoundary, ImageMeta
from substitute.presentation.canvas.output.output_grid_reflow_context import (
    OutputGridReflowContextResolver,
    OutputSceneOverviewGridContext,
    OutputSourceGridContext,
)


def test_source_grid_context_uses_current_session_route_and_source() -> None:
    """A current set-zero source should resolve its authorized session token."""

    source = _source("source-a")
    session = _session(OutputCanvasProjection((source,), "source-a", 0, None, 1))
    resolver = _resolver(session=session, sources={"source-a": source})

    context = resolver.current_context()

    assert isinstance(context, OutputSourceGridContext)
    assert context.session_token == session.token()
    assert context.source is source


def test_declared_multiscene_overview_allows_one_current_scene_tile() -> None:
    """An in-progress declared scene batch should present its first available scene."""

    source = _source("source-a")
    scene = OutputCanvasSceneGroup("run-a", "scene-a", "Scene A", 0, (source,))
    projection = OutputCanvasProjection(
        sources=(source,),
        active_source_key=None,
        active_set_index=1,
        active_uuid=None,
        set_count=1,
        scene_groups=(scene,),
        active_scene_key="scene-a",
        active_scene_overview=True,
        scene_count=5,
    )
    session = _session(projection)
    resolver = _resolver(
        session=session,
        scenes={"scene-a": scene},
        overview=True,
        scene_key="scene-a",
    )

    context = resolver.current_context()

    assert isinstance(context, OutputSceneOverviewGridContext)
    assert context.scenes == (scene,)


def test_compare_and_foreign_route_contexts_fail_closed() -> None:
    """Compare state and route mismatches should never schedule grid mutation."""

    source = _source("source-a")
    session = _session(OutputCanvasProjection((source,), "source-a", 0, None, 1))

    assert (
        _resolver(
            session=session,
            sources={"source-a": source},
            compare=True,
        ).current_context()
        is None
    )
    assert (
        _resolver(
            session=session,
            sources={"source-a": source},
            source_key="source-b",
        ).current_context()
        is None
    )


def _resolver(
    *,
    session: OutputCanvasSession,
    sources: dict[str, OutputCanvasSourceGroup] | None = None,
    scenes: dict[str, OutputCanvasSceneGroup] | None = None,
    compare: bool = False,
    overview: bool = False,
    scene_key: str | None = None,
    source_key: str = "source-a",
) -> OutputGridReflowContextResolver:
    """Build a context resolver from deterministic current state."""

    return OutputGridReflowContextResolver(
        output_session=lambda: session,
        scene_groups=lambda: scenes or {},
        source_groups=lambda: sources or {},
        compare_enabled=lambda: compare,
        scene_overview_active=lambda: overview,
        active_scene_key=lambda: scene_key,
        active_source_key=lambda: source_key,
        active_set_index=lambda: 0,
    )


def _session(projection: OutputCanvasProjection) -> OutputCanvasSession:
    """Bind one projection to a real session boundary."""

    return bind_output_canvas_session(
        CanvasSessionBoundary(),
        workflow_id="wf",
        projection=projection,
        image_metadata_lookup={
            item.image_id: item.image_meta
            for source in projection.sources
            for item in source.images_by_set.values()
        },
    )


def _source(source_key: str) -> OutputCanvasSourceGroup:
    """Build one source group with a cached final image identity."""

    image_id = uuid4()
    return OutputCanvasSourceGroup(
        source_key,
        "Source",
        {
            1: OutputCanvasImageItem(
                image_id,
                ImageMeta("wf", "Source", 1, "", "E:/output.png"),
                1,
            )
        },
    )

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

"""Verify Output canvas route-state host adapters."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasProjection,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_preview_lifecycle_service import (
    OutputCanvasRevisionCache,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewLane,
    OutputPreviewLaneKey,
    OutputPreviewRegistry,
)
from substitute.domain.workflow import CanvasSessionRevision, ImageMeta
from substitute.presentation.canvas.output.output_canvas_route_state import (
    output_route_state_snapshot,
    output_scene_groups_by_key,
    visible_output_source_groups_by_key,
)


def test_output_scene_groups_by_key_overlays_preview_scenes() -> None:
    """Route-state adapter should include preview-only scene groups."""

    final_scene = _scene("scene-a", _source("final", _item(uuid4(), 1)))
    preview_id = uuid4()
    preview_scene = _scene("scene-b", _source("preview", _item(uuid4(), 1)))
    cache = OutputCanvasRevisionCache(
        registry=OutputPreviewRegistry(),
        session=None,
    )
    scene_lane_key = OutputPreviewLaneKey.scene(
        workflow_id="wf",
        generation_run_id="run",
        prompt_id="prompt",
        source_key="preview",
        scene_run_id="run",
        scene_key="scene-b",
    )
    cache.registry._lanes[scene_lane_key] = OutputPreviewLane(
        key=scene_lane_key,
        preview_id=preview_id,
        image=object(),
        source_label="preview",
        client_id="client",
        session_revision=CanvasSessionRevision(1),
        scene_title=preview_scene.title,
        scene_order=preview_scene.order,
    )
    host = SimpleNamespace(
        _output_projection=OutputCanvasProjection(
            sources=(),
            active_source_key=None,
            active_set_index=1,
            active_uuid=None,
            set_count=0,
            scene_groups=(final_scene,),
        ),
        _revision_cache=cache,
    )

    scene_groups = output_scene_groups_by_key(output_route_state_snapshot(host))

    assert scene_groups["scene-a"] == final_scene
    assert scene_groups["scene-b"].scene_key == "scene-b"
    assert scene_groups["scene-b"].preview_image_id == preview_id
    assert scene_groups["scene-b"].representative_source_key == "preview"


def test_visible_output_source_groups_by_key_scopes_to_active_scene() -> None:
    """Route-state adapter should expose only active-scene sources."""

    source_a = _source("source-a", _item(uuid4(), 1))
    source_b = _source("source-b", _item(uuid4(), 1))
    scene_b = _scene("scene-b", source_b)
    host = SimpleNamespace(
        _output_projection=OutputCanvasProjection(
            sources=(source_a, source_b),
            active_source_key=None,
            active_set_index=1,
            active_uuid=None,
            set_count=1,
            scene_groups=(scene_b,),
        ),
        _revision_cache=OutputCanvasRevisionCache(
            registry=OutputPreviewRegistry(),
            session=None,
        ),
        active_scene_overview=False,
        active_scene_key="scene-b",
        scene_count=2,
    )

    assert visible_output_source_groups_by_key(output_route_state_snapshot(host)) == {
        "source-b": source_b
    }


def _item(image_id: UUID, set_index: int) -> OutputCanvasImageItem:
    """Return one output image item for route-state tests."""

    return OutputCanvasImageItem(
        image_id=image_id,
        image_meta=ImageMeta("wf", "Cube", set_index, "", "E:/out.png"),
        set_index=set_index,
    )


def _source(
    source_key: str,
    *items: OutputCanvasImageItem,
) -> OutputCanvasSourceGroup:
    """Return one source group keyed by each item's set index."""

    return OutputCanvasSourceGroup(
        source_key=source_key,
        label=source_key,
        images_by_set={item.set_index: item for item in items},
    )


def _scene(
    scene_key: str,
    *sources: OutputCanvasSourceGroup,
) -> OutputCanvasSceneGroup:
    """Return one scene group for route-state tests."""

    return OutputCanvasSceneGroup(
        scene_run_id="run",
        scene_key=scene_key,
        title=scene_key,
        order=1,
        sources=sources,
    )

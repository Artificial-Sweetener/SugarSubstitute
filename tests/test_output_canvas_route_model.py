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

"""Contract tests for pure output canvas route resolution."""

from __future__ import annotations

from uuid import UUID, uuid4

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasProjection,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.domain.workflow import ImageMeta
from substitute.presentation.canvas.output.output_canvas_route_model import (
    OutputCanvasRouteModel,
)


def test_route_model_resolves_previous_source_when_still_available() -> None:
    """Previous source focus should survive reprojection when allowed."""

    source_a = _source("a", _item(uuid4(), 1))
    source_b = _source("b", _item(uuid4(), 1))
    sources = {source.source_key: source for source in (source_a, source_b)}

    result = OutputCanvasRouteModel.resolved_active_source_key(
        sources,
        "a",
        previous_source_key="b",
        preserve_previous=True,
    )

    assert result == "b"


def test_route_model_scopes_sources_to_active_scene() -> None:
    """Multi-scene projections should expose only the selected scene's sources."""

    source_a = _source("a", _item(uuid4(), 1))
    source_b = _source("b", _item(uuid4(), 1))
    scene = OutputCanvasSceneGroup(
        scene_run_id="run",
        scene_key="scene-b",
        title="Scene B",
        order=1,
        sources=(source_b,),
    )
    projection = OutputCanvasProjection(
        sources=(source_a, source_b),
        active_source_key=None,
        active_set_index=1,
        active_uuid=None,
        set_count=1,
        scene_groups=(scene,),
        active_scene_key="scene-b",
        scene_count=2,
    )

    result = OutputCanvasRouteModel.sources_for_active_scene(
        projection,
        scene_groups={scene.scene_key: scene},
        scene_count=2,
        active_scene_key="scene-b",
    )

    assert result == (source_b,)


def test_route_model_keeps_final_scene_when_overlaying_preview_groups() -> None:
    """Preview scene groups should fill missing scenes without replacing finals."""

    final_scene = OutputCanvasSceneGroup(
        scene_run_id="run-final",
        scene_key="scene-a",
        title="Scene A",
        order=0,
        sources=(_source("final", _item(uuid4(), 1)),),
    )
    preview_scene_a = OutputCanvasSceneGroup(
        scene_run_id="run-preview",
        scene_key="scene-a",
        title="Preview Scene A",
        order=0,
        sources=(_source("preview-a", _item(uuid4(), 1)),),
    )
    preview_scene_b = OutputCanvasSceneGroup(
        scene_run_id="run-preview",
        scene_key="scene-b",
        title="Preview Scene B",
        order=1,
        sources=(_source("preview-b", _item(uuid4(), 1)),),
    )
    projection = OutputCanvasProjection(
        sources=(),
        active_source_key=None,
        active_set_index=1,
        active_uuid=None,
        set_count=1,
        scene_groups=(final_scene,),
    )

    result = OutputCanvasRouteModel.scene_groups_by_key(
        projection,
        preview_scene_groups_by_key={
            "scene-a": preview_scene_a,
            "scene-b": preview_scene_b,
        },
    )

    assert result == {"scene-a": final_scene, "scene-b": preview_scene_b}


def test_route_model_visible_sources_follow_scene_and_overview_state() -> None:
    """Visible source groups should reflect active scene and overview selection."""

    source_a = _source("a", _item(uuid4(), 1))
    source_b = _source("b", _item(uuid4(), 1))
    scene_b = OutputCanvasSceneGroup(
        scene_run_id="run",
        scene_key="scene-b",
        title="Scene B",
        order=1,
        sources=(source_b,),
    )
    projection = OutputCanvasProjection(
        sources=(source_a, source_b),
        active_source_key=None,
        active_set_index=1,
        active_uuid=None,
        set_count=1,
        scene_groups=(scene_b,),
    )

    visible = OutputCanvasRouteModel.visible_source_groups_by_key(
        projection,
        scene_groups_by_key={"scene-b": scene_b},
        active_scene_overview=False,
        active_scene_key="scene-b",
        scene_count=2,
    )
    overview_visible = OutputCanvasRouteModel.visible_source_groups_by_key(
        projection,
        scene_groups_by_key={"scene-b": scene_b},
        active_scene_overview=True,
        active_scene_key="scene-b",
        scene_count=2,
    )

    assert visible == {"b": source_b}
    assert overview_visible == {}


def test_route_model_visible_sources_support_preview_only_scene_groups() -> None:
    """Preview-only scenes should supply sources before a projection arrives."""

    source = _source("preview", _item(uuid4(), 1))
    preview_scene = OutputCanvasSceneGroup(
        scene_run_id="run-preview",
        scene_key="scene-preview",
        title="Preview Scene",
        order=0,
        sources=(source,),
    )

    result = OutputCanvasRouteModel.visible_source_groups_by_key(
        None,
        scene_groups_by_key={"scene-preview": preview_scene},
        active_scene_overview=False,
        active_scene_key="scene-preview",
        scene_count=1,
    )

    assert result == {"preview": source}


def test_route_model_returns_declarative_route_commands() -> None:
    """Route command resolution should avoid QPane or widget dependencies."""

    image_id = uuid4()

    assert (
        OutputCanvasRouteModel.route_command_for_selection(
            active_scene_overview=True,
            scene_count=2,
            active_set_index=1,
            active_source_key=None,
            active_scene_key=None,
            active_image_id=None,
        ).kind
        == "scene_overview"
    )
    grid_command = OutputCanvasRouteModel.route_command_for_selection(
        active_scene_overview=False,
        scene_count=1,
        active_set_index=0,
        active_source_key="source",
        active_scene_key=None,
        active_image_id=None,
    )
    image_command = OutputCanvasRouteModel.route_command_for_selection(
        active_scene_overview=False,
        scene_count=1,
        active_set_index=1,
        active_source_key="source",
        active_scene_key=None,
        active_image_id=image_id,
    )

    assert grid_command.kind == "source_grid"
    assert grid_command.source_key == "source"
    assert image_command.kind == "image"
    assert image_command.image_id == image_id


def test_route_model_resolves_concrete_set_from_active_source() -> None:
    """Set selector changes should prefer the current source when it has an item."""

    source_a_item = _item(uuid4(), 2)
    source_b_item = _item(uuid4(), 2)
    sources = {
        "a": _source("a", source_a_item),
        "b": _source("b", source_b_item),
    }

    result = OutputCanvasRouteModel.concrete_set_selection(
        sources,
        active_source_key="a",
        set_index=2,
    )

    assert result == ("a", source_a_item)


def test_route_model_rejects_set_when_active_source_is_unavailable() -> None:
    """Set selector changes must retain the current CubeOutput identity."""

    source_b_item = _item(uuid4(), 2)
    sources = {
        "a": _source("a", _item(uuid4(), 1)),
        "b": _source("b", source_b_item),
    }

    result = OutputCanvasRouteModel.concrete_set_selection(
        sources,
        active_source_key="missing-source",
        set_index=2,
    )

    assert result is None


def test_route_model_does_not_approximate_explicit_set_on_active_source() -> None:
    """Explicit batch selection should not cross sources or choose a neighbor."""

    source_a_item = _item(uuid4(), 1)
    source_b_item = _item(uuid4(), 2)
    sources = {
        "a": _source("a", source_a_item),
        "b": _source("b", source_b_item),
    }

    result = OutputCanvasRouteModel.concrete_set_selection(
        sources,
        active_source_key="a",
        set_index=2,
    )

    assert result is None


def test_route_model_returns_none_when_concrete_set_has_no_item() -> None:
    """Set selector changes without any matching item should not activate output."""

    result = OutputCanvasRouteModel.concrete_set_selection(
        {"a": _source("a")},
        active_source_key="a",
        set_index=4,
    )

    assert result is None


def test_route_model_distinguishes_renderable_grid_from_batch_overview() -> None:
    """A one-image source can render a grid without offering batch navigation."""

    one_item = _source("one", _item(uuid4(), 1))
    batch = _source("batch", _item(uuid4(), 1), _item(uuid4(), 2))

    assert OutputCanvasRouteModel.grid_available_for_source(one_item) is True
    assert OutputCanvasRouteModel.batch_overview_available_for_source(one_item) is False
    assert OutputCanvasRouteModel.batch_overview_available_for_source(batch) is True


def test_route_model_finds_first_source_with_batch_overview() -> None:
    """Batch-overview routing should skip renderable one-image sources."""

    sources = {
        "one": _source("one", _item(uuid4(), 1)),
        "batch": _source("batch", _item(uuid4(), 1), _item(uuid4(), 2)),
    }

    assert OutputCanvasRouteModel.first_batch_overview_source_key(sources) == "batch"


def _item(image_id: UUID, set_index: int) -> OutputCanvasImageItem:
    """Return one output image item for route-model tests."""

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

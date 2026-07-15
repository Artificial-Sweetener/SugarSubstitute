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

"""Verify generic responsive Output grid QPane request construction."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteIdentity,
)
from substitute.presentation.canvas.output.output_grid_scene_builder import (
    OutputGridSceneBuilder,
    OutputGridTile,
)
from substitute.presentation.canvas.shared.responsive_canvas_grid_policy import (
    CanvasViewportExtent,
)

_LAYER_NAMESPACE = UUID("39ba8753-5fef-4270-89c8-90f78401993a")


def test_builder_centers_aspect_fitted_tiles_and_keeps_uniform_bounds() -> None:
    """Layer placements should fit source aspect inside centered uniform cells."""

    first_id = uuid4()
    second_id = uuid4()
    route = CanvasRouteIdentity("source_grid", "scene:;source:a;set:0")
    plan = OutputGridSceneBuilder().build(
        route=route,
        title="Grid",
        tiles=(
            _tile(first_id, 512, 768, 1),
            _tile(second_id, 768, 512, 2),
        ),
        viewport_extent=CanvasViewportExtent(1400.0, 700.0),
    )

    assert plan is not None
    request = cast(Any, plan.request)
    assert len(request.layers) == 2
    assert request.bounds.width() > 0.0
    assert request.bounds.height() > 0.0
    assert request.layers[0].placement.width() / request.layers[
        0
    ].placement.height() == (512 / 768)
    assert request.layers[1].placement.width() / request.layers[
        1
    ].placement.height() == (768 / 512)


def test_builder_signature_ignores_viewport_when_topology_is_unchanged() -> None:
    """Equivalent topology should retain one content/layout signature."""

    image_id = uuid4()
    route = CanvasRouteIdentity("source_grid", "scene:;source:a;set:0")
    builder = OutputGridSceneBuilder()
    tiles = (_tile(image_id, 512, 768, 1),)

    first = builder.build(
        route=route,
        title="Grid",
        tiles=tiles,
        viewport_extent=CanvasViewportExtent(800.0, 600.0),
    )
    second = builder.build(
        route=route,
        title="Grid",
        tiles=tiles,
        viewport_extent=CanvasViewportExtent(1600.0, 1200.0),
    )

    assert first is not None and second is not None
    assert first.layout_signature == second.layout_signature
    assert first.request.layers[0].layer_id == second.request.layers[0].layer_id


def _tile(image_id: UUID, width: int, height: int, set_index: int) -> OutputGridTile:
    """Return one measurable generic grid tile."""

    image = SimpleNamespace(
        size=lambda: SimpleNamespace(width=lambda: width, height=lambda: height)
    )
    return OutputGridTile(
        image_id=image_id,
        image=image,
        layer_namespace=_LAYER_NAMESPACE,
        layer_identity_seed=f"image:{image_id}",
        role="final-output",
        metadata={"set_index": set_index},
        content_key=("batch", str(image_id), set_index, width, height),
    )

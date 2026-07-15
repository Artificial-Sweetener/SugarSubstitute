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

"""Verify pure responsive canvas grid topology selection."""

from __future__ import annotations

import math

import pytest

from substitute.presentation.canvas.shared.responsive_canvas_grid_policy import (
    CanvasGridTileExtent,
    CanvasViewportExtent,
    GRID_AREA_TOLERANCE,
    ResponsiveCanvasGridPolicy,
    ResponsiveGridRequest,
    grid_gutter_for_dimensions,
)


@pytest.mark.parametrize("tile_count", [*range(1, 33), 64, 100])
@pytest.mark.parametrize(
    "tile_extent",
    [
        CanvasGridTileExtent(512.0, 512.0),
        CanvasGridTileExtent(512.0, 768.0),
        CanvasGridTileExtent(768.0, 512.0),
    ],
)
@pytest.mark.parametrize(
    "viewport",
    [
        CanvasViewportExtent(1600.0, 700.0),
        CanvasViewportExtent(1000.0, 1000.0),
        CanvasViewportExtent(700.0, 1600.0),
    ],
)
def test_policy_selects_maximum_displayed_tile_area(
    tile_count: int,
    tile_extent: CanvasGridTileExtent,
    viewport: CanvasViewportExtent,
) -> None:
    """Every valid request should select a globally maximal candidate."""

    decision = ResponsiveCanvasGridPolicy().choose(
        ResponsiveGridRequest(tile_count, tile_extent, viewport)
    )

    assert decision is not None
    chosen_area = decision.candidate.displayed_tile_area
    for columns in range(1, tile_count + 1):
        rows = math.ceil(tile_count / columns)
        gutter = grid_gutter_for_dimensions(tile_extent, (columns, rows))
        scene_width = columns * tile_extent.width + (columns - 1) * gutter
        scene_height = rows * tile_extent.height + (rows - 1) * gutter
        scale = min(
            viewport.width / scene_width,
            viewport.height / scene_height,
        )
        candidate_area = tile_extent.width * tile_extent.height * scale * scale
        assert chosen_area + GRID_AREA_TOLERANCE >= candidate_area


@pytest.mark.parametrize(
    "grid_request",
    [
        ResponsiveGridRequest(
            0, CanvasGridTileExtent(1.0, 1.0), CanvasViewportExtent(1.0, 1.0)
        ),
        ResponsiveGridRequest(
            1, CanvasGridTileExtent(0.0, 1.0), CanvasViewportExtent(1.0, 1.0)
        ),
        ResponsiveGridRequest(
            1, CanvasGridTileExtent(1.0, 1.0), CanvasViewportExtent(0.0, 1.0)
        ),
        ResponsiveGridRequest(
            1,
            CanvasGridTileExtent(float("nan"), 1.0),
            CanvasViewportExtent(1.0, 1.0),
        ),
    ],
)
def test_policy_rejects_invalid_requests(grid_request: ResponsiveGridRequest) -> None:
    """Invalid resize geometry should return no decision without raising."""

    assert ResponsiveCanvasGridPolicy().choose(grid_request) is None


def test_policy_retains_then_releases_previous_shape_at_two_percent() -> None:
    """Topology hysteresis should retain near a breakpoint and release beyond it."""

    policy = ResponsiveCanvasGridPolicy()
    tile = CanvasGridTileExtent(512.0, 512.0)
    near = policy.choose(
        ResponsiveGridRequest(2, tile, CanvasViewportExtent(1009.0, 1000.0)),
        previous_dimensions=(1, 2),
    )
    far = policy.choose(
        ResponsiveGridRequest(2, tile, CanvasViewportExtent(1400.0, 1000.0)),
        previous_dimensions=(1, 2),
    )

    assert near is not None
    assert near.candidate.dimensions == (1, 2)
    assert near.retained_previous_shape is True
    assert far is not None
    assert far.candidate.dimensions == (2, 1)
    assert far.retained_previous_shape is False


def test_equivalent_dpr_scaled_extents_select_same_topology() -> None:
    """Equivalent physical scaling should not change responsive topology."""

    policy = ResponsiveCanvasGridPolicy()
    first = policy.choose(
        ResponsiveGridRequest(
            7,
            CanvasGridTileExtent(512.0, 768.0),
            CanvasViewportExtent(900.0, 600.0),
        )
    )
    second = policy.choose(
        ResponsiveGridRequest(
            7,
            CanvasGridTileExtent(1024.0, 1536.0),
            CanvasViewportExtent(1800.0, 1200.0),
        )
    )

    assert first is not None and second is not None
    assert first.candidate.dimensions == second.candidate.dimensions

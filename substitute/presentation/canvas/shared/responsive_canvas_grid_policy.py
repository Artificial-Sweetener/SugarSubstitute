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

"""Choose responsive canvas grid topology from physical viewport geometry."""

from __future__ import annotations

import math
from dataclasses import dataclass

GRID_MIN_GUTTER = 2.0
GRID_GUTTER_SCENE_RATIO = 1.0 / 512.0
GRID_AREA_TOLERANCE = 1e-9
GRID_TOPOLOGY_HYSTERESIS_RATIO = 1.02


@dataclass(frozen=True, slots=True)
class CanvasViewportExtent:
    """Describe a physical QPane viewport extent."""

    width: float
    height: float

    @property
    def valid(self) -> bool:
        """Return whether both dimensions are positive and finite."""

        return _positive_finite(self.width) and _positive_finite(self.height)


@dataclass(frozen=True, slots=True)
class CanvasGridTileExtent:
    """Describe the reference tile extent used for topology scoring."""

    width: float
    height: float

    @property
    def valid(self) -> bool:
        """Return whether both dimensions are positive and finite."""

        return _positive_finite(self.width) and _positive_finite(self.height)


@dataclass(frozen=True, slots=True)
class ResponsiveGridRequest:
    """Describe one pure responsive topology decision."""

    tile_count: int
    tile_extent: CanvasGridTileExtent
    viewport_extent: CanvasViewportExtent


@dataclass(frozen=True, slots=True)
class ResponsiveGridCandidate:
    """Describe one scored grid-shape candidate."""

    dimensions: tuple[int, int]
    gutter: float
    scene_width: float
    scene_height: float
    display_scale: float
    displayed_tile_area: float
    empty_cells: int


@dataclass(frozen=True, slots=True)
class ResponsiveGridDecision:
    """Describe the selected candidate and hysteresis outcome."""

    candidate: ResponsiveGridCandidate
    retained_previous_shape: bool


class ResponsiveCanvasGridPolicy:
    """Select the grid shape that displays uniform tiles at maximum area."""

    def choose(
        self,
        request: ResponsiveGridRequest,
        previous_dimensions: tuple[int, int] | None = None,
    ) -> ResponsiveGridDecision | None:
        """Return the deterministic best topology for a valid request."""

        if (
            request.tile_count <= 0
            or not request.tile_extent.valid
            or not request.viewport_extent.valid
        ):
            return None
        candidates = tuple(
            _candidate(request, columns) for columns in range(1, request.tile_count + 1)
        )
        best = candidates[0]
        for candidate in candidates[1:]:
            if _candidate_is_better(candidate, best, request.tile_extent):
                best = candidate
        previous = next(
            (
                candidate
                for candidate in candidates
                if candidate.dimensions == previous_dimensions
            ),
            None,
        )
        if previous is not None and previous.displayed_tile_area > 0.0:
            improvement = best.displayed_tile_area / previous.displayed_tile_area
            if improvement < GRID_TOPOLOGY_HYSTERESIS_RATIO:
                return ResponsiveGridDecision(previous, retained_previous_shape=True)
        return ResponsiveGridDecision(best, retained_previous_shape=False)


def grid_gutter_for_dimensions(
    tile_extent: CanvasGridTileExtent,
    dimensions: tuple[int, int],
) -> float:
    """Return proportional scene-unit spacing for one candidate topology."""

    columns, rows = dimensions
    if not tile_extent.valid or columns <= 0 or rows <= 0:
        return GRID_MIN_GUTTER
    horizontal_span = columns * tile_extent.width
    vertical_span = rows * tile_extent.height
    if horizontal_span >= vertical_span:
        packed_span = horizontal_span
        gap_count = max(0, columns - 1)
    else:
        packed_span = vertical_span
        gap_count = max(0, rows - 1)
    denominator = 1.0 - GRID_GUTTER_SCENE_RATIO * gap_count
    if denominator <= 0.0:
        return GRID_MIN_GUTTER
    return max(
        GRID_MIN_GUTTER,
        GRID_GUTTER_SCENE_RATIO * packed_span / denominator,
    )


def _candidate(request: ResponsiveGridRequest, columns: int) -> ResponsiveGridCandidate:
    """Build one scored candidate for the requested column count."""

    rows = math.ceil(request.tile_count / columns)
    dimensions = (columns, rows)
    gutter = grid_gutter_for_dimensions(request.tile_extent, dimensions)
    scene_width = columns * request.tile_extent.width + (columns - 1) * gutter
    scene_height = rows * request.tile_extent.height + (rows - 1) * gutter
    display_scale = min(
        request.viewport_extent.width / scene_width,
        request.viewport_extent.height / scene_height,
    )
    displayed_tile_area = (
        request.tile_extent.width
        * request.tile_extent.height
        * display_scale
        * display_scale
    )
    return ResponsiveGridCandidate(
        dimensions=dimensions,
        gutter=gutter,
        scene_width=scene_width,
        scene_height=scene_height,
        display_scale=display_scale,
        displayed_tile_area=displayed_tile_area,
        empty_cells=columns * rows - request.tile_count,
    )


def _candidate_is_better(
    candidate: ResponsiveGridCandidate,
    current: ResponsiveGridCandidate,
    tile_extent: CanvasGridTileExtent,
) -> bool:
    """Return whether one responsive candidate wins deterministic ordering."""

    area_delta = candidate.displayed_tile_area - current.displayed_tile_area
    if area_delta > GRID_AREA_TOLERANCE:
        return True
    if area_delta < -GRID_AREA_TOLERANCE:
        return False
    if candidate.empty_cells != current.empty_cells:
        return candidate.empty_cells < current.empty_cells
    candidate_bias = _orientation_bias(candidate.dimensions, tile_extent)
    current_bias = _orientation_bias(current.dimensions, tile_extent)
    if candidate_bias != current_bias:
        return candidate_bias < current_bias
    return candidate.dimensions[0] < current.dimensions[0]


def _orientation_bias(
    dimensions: tuple[int, int], tile_extent: CanvasGridTileExtent
) -> int:
    """Score topology orientation against the reference tile orientation."""

    columns, rows = dimensions
    if tile_extent.width < tile_extent.height:
        return max(0, columns - rows)
    if tile_extent.width > tile_extent.height:
        return max(0, rows - columns)
    return abs(columns - rows)


def _positive_finite(value: float) -> bool:
    """Return whether a numeric dimension is positive and finite."""

    return math.isfinite(value) and value > 0.0


__all__ = [
    "CanvasGridTileExtent",
    "CanvasViewportExtent",
    "GRID_AREA_TOLERANCE",
    "GRID_GUTTER_SCENE_RATIO",
    "GRID_MIN_GUTTER",
    "GRID_TOPOLOGY_HYSTERESIS_RATIO",
    "ResponsiveCanvasGridPolicy",
    "ResponsiveGridCandidate",
    "ResponsiveGridDecision",
    "ResponsiveGridRequest",
    "grid_gutter_for_dimensions",
]

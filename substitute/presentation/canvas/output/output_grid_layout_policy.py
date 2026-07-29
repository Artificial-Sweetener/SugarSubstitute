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

"""Describe the established packed presentation for Output document grids."""

from __future__ import annotations

from cutecanvas import (
    IncompleteRowAlignment,
    ResponsiveGridPacking,
    ResponsiveGridPolicy,
    ResponsiveGridTopology,
)

_OUTPUT_NATIVE_TILE_GAP_RATIO = 1.0 / 512.0
_OUTPUT_NATIVE_TILE_MINIMUM_GAP = 2.0
_OUTPUT_TOPOLOGY_HYSTERESIS_RATIO = 1.02


def output_grid_layout_policy() -> ResponsiveGridPolicy:
    """Return the responsive policy that preserves Output's native tile packing."""

    return ResponsiveGridPolicy(
        topology=ResponsiveGridTopology.MAXIMUM_REFERENCE_AREA,
        topology_hysteresis_ratio=_OUTPUT_TOPOLOGY_HYSTERESIS_RATIO,
        incomplete_row_alignment=IncompleteRowAlignment.CENTER,
        packing=ResponsiveGridPacking.NATIVE_TILES,
        native_tile_gap_ratio=_OUTPUT_NATIVE_TILE_GAP_RATIO,
        native_tile_minimum_gap=_OUTPUT_NATIVE_TILE_MINIMUM_GAP,
    )


__all__ = ["output_grid_layout_policy"]

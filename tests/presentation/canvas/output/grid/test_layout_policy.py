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

"""Verify Output's responsive grid policy preserves baseline packing semantics."""

from __future__ import annotations

from cutecanvas import (
    IncompleteRowAlignment,
    ResponsiveGridPacking,
    ResponsiveGridTopology,
)

from substitute.presentation.canvas.output.output_grid_layout_policy import (
    output_grid_layout_policy,
)


def test_output_grid_policy_freezes_baseline_packed_native_contract() -> None:
    """Keep the legacy topology, hysteresis, alignment, and gutter policy explicit."""

    policy = output_grid_layout_policy()

    assert policy.topology is ResponsiveGridTopology.MAXIMUM_REFERENCE_AREA
    assert policy.topology_hysteresis_ratio == 1.02
    assert policy.incomplete_row_alignment is IncompleteRowAlignment.CENTER
    assert policy.packing is ResponsiveGridPacking.NATIVE_TILES
    assert policy.native_tile_gap_ratio == 1.0 / 512.0
    assert policy.native_tile_minimum_gap == 2.0

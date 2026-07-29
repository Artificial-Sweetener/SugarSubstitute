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

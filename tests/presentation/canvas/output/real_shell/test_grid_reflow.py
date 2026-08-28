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

"""Verify responsive Output grid geometry and route-safe resize behavior."""

from __future__ import annotations


from pytest import approx

from tests.presentation.canvas.output.real_shell.grid_support import (
    grid_dimensions,
    horizontal_gap_in_native_scene_units,
    wait_for_new_grid_snapshot,
)
from tests.support.real_output_canvas.harness import RealShellOutputCanvasHarness
from tests.support.real_output_canvas.models import OutputSpec


def test_source_grid_preserves_baseline_packed_gutters_across_stable_reflow(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Keep Output's baseline native gutter when size changes retain topology."""

    harness.add_workflow("alpha", activate=True)
    run = harness.start_run("alpha")
    for index in range(3):
        harness.emit_output(
            run,
            OutputSpec(
                "source",
                "Source",
                (80 + index * 30, 40, 160),
                list_index=index,
                width=1144,
                height=1608,
            ),
        )
    harness.wait_for_output_count("alpha", 3)
    expected_scene_gutter = max(2.0, 3216.0 / 511.0)
    workspace = harness.shell.output_canvas.workspace
    previous_snapshot = workspace.gridSnapshot()
    harness.set_output_viewport_extent(848.0, 946.0)
    first_snapshot = wait_for_new_grid_snapshot(harness, previous_snapshot)
    assert (first_snapshot.columns, first_snapshot.rows) == (2, 2)
    first_gap = horizontal_gap_in_native_scene_units(
        first_snapshot,
        native_width=1144.0,
    )

    previous_snapshot = workspace.gridSnapshot()
    harness.set_output_viewport_extent(856.0, 954.0)
    second_snapshot = wait_for_new_grid_snapshot(harness, previous_snapshot)
    assert (second_snapshot.columns, second_snapshot.rows) == (2, 2)
    second_gap = horizontal_gap_in_native_scene_units(
        second_snapshot,
        native_width=1144.0,
    )

    assert first_gap == approx(expected_scene_gutter, abs=0.1)
    assert second_gap == approx(expected_scene_gutter, abs=0.1)
    assert second_gap == approx(first_gap, abs=0.01)


def test_five_landscape_tiles_reflow_across_wide_square_and_tall_extents(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Five cached landscape tiles should choose a topology for each canvas shape."""

    harness.add_workflow("alpha", activate=True)
    run = harness.start_run("alpha")
    for index in range(5):
        harness.emit_output(
            run,
            OutputSpec(
                "shared-five",
                "Shared Five",
                (30 + index * 25, 80, 180),
                list_index=index,
                width=96,
                height=48,
            ),
        )
    harness.wait_for_output_count("alpha", 5)
    harness.wait_until(lambda: len(harness.fingerprint().grid_target_frames) == 5)
    observed: list[tuple[int, int] | None] = []
    for width, height in ((1400.0, 450.0), (800.0, 800.0), (450.0, 1400.0)):
        previous_snapshot = harness.shell.output_canvas.workspace.gridSnapshot()
        harness.set_output_viewport_extent(width, height)
        wait_for_new_grid_snapshot(harness, previous_snapshot)
        observed.append(grid_dimensions(harness.fingerprint()))

    assert observed[0] != observed[-1]
    assert all(
        dimensions is not None and dimensions[0] * dimensions[1] >= 5
        for dimensions in observed
    )


def test_grid_resize_then_workflow_switch_preserves_new_route(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Switching workflows after a grid resize must retain the new route."""

    harness.add_workflow("alpha", activate=True)
    harness.add_workflow("beta")
    alpha_run = harness.start_run("alpha")
    for index in range(2):
        harness.emit_output(
            alpha_run,
            OutputSpec(
                "alpha-grid",
                "Alpha Grid",
                (180, 30 + index * 50, 30),
                list_index=index,
            ),
        )
    harness.wait_for_output_count("alpha", 2)
    beta_run = harness.start_run("beta")
    harness.emit_output(beta_run, OutputSpec("beta", "Beta", (30, 30, 210)))
    harness.wait_for_output_count("beta", 1)
    harness.activate_workflow("alpha")
    harness.set_output_viewport_extent(1400.0, 420.0)

    harness.activate_workflow("beta")

    harness.assert_showing_workflow("beta", color=(30, 30, 210))
    harness.assert_not_showing_workflow("alpha")


def test_comparison_route_survives_workspace_resize(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Workspace resize must not replace an active comparison presentation."""

    harness.add_workflow("alpha", activate=True)
    run = harness.start_run("alpha")
    for index in range(2):
        harness.emit_output(
            run,
            OutputSpec(
                "alpha-grid",
                "Alpha Grid",
                (40 + index * 120, 80, 180),
                list_index=index,
            ),
        )
    harness.wait_for_output_count("alpha", 2)
    canvas = harness.shell.output_canvas
    first_image_id = harness.output_ids("alpha")[0]
    harness.select_output_id(first_image_id)
    harness.wait_until(lambda: harness.fingerprint().active_image_id == first_image_id)
    second_image_id = harness.output_ids("alpha")[1]
    assert canvas.document.present_comparison(
        first_image_id,
        second_image_id,
        split_position=0.5,
        orientation="vertical",
    )
    before = harness.fingerprint().active_composition_id

    harness.set_output_viewport_extent(400.0, 1200.0)

    assert canvas.document.session.presentation.kind.value == "comparison"
    assert harness.fingerprint().active_composition_id == before

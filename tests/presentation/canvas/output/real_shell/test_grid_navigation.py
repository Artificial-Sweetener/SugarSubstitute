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

"""Verify Output grid hierarchy, navigation, and responsive presentation."""

from __future__ import annotations

from tests.presentation.canvas.output.real_shell.grid_support import (
    grid_dimensions,
    wait_for_new_grid_snapshot,
)
from tests.support.real_output_canvas.harness import RealShellOutputCanvasHarness
from tests.support.real_output_canvas.models import OutputSpec, SceneSpec


def test_out_of_order_batch_arrivals_converge_to_active_workflow_route(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Handle batch index 1 arriving before batch index 0."""

    harness.add_workflow("alpha", activate=True)
    run = harness.start_run("alpha")

    harness.emit_output(
        run,
        OutputSpec("alpha-batch", "Alpha Batch", (30, 170, 170), list_index=1),
    )
    harness.emit_output(
        run,
        OutputSpec("alpha-batch", "Alpha Batch", (170, 170, 30), list_index=0),
    )
    harness.wait_for_output_count("alpha", 2)

    harness.assert_scene_composition_for_workflow("alpha")


def test_unequal_scene_sources_navigate_exact_batches_and_grid(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Drill from scene to sibling batch grid and then a concrete Cube output."""

    harness.add_workflow("alpha", activate=True)
    harness.show_canvas("Output")
    expected_output_count = 0
    for scene_index in range(3):
        run = harness.start_run("alpha", run_index=scene_index + 1)
        scene = SceneSpec(
            run_id="scene-run-alpha",
            key=f"scene{scene_index + 1}",
            title=f"scene{scene_index + 1}",
            order=scene_index,
            count=3,
        )
        for batch_index, color in enumerate(
            ((210, 40, 40), (40, 210, 40), (40, 40, 210))
        ):
            harness.emit_output(
                run,
                OutputSpec(
                    "alpha:text",
                    "Text to Image",
                    color,
                    list_index=0,
                    batch_index=batch_index,
                    scene=scene,
                ),
            )
        harness.emit_output(
            run,
            OutputSpec(
                "alpha:upscale",
                "Diffusion Upscale",
                (150, 150, 150),
                list_index=0,
                batch_index=0,
                scene=scene,
            ),
        )
        expected_output_count += 4
        harness.wait_for_output_count("alpha", expected_output_count)
        harness.complete_run(run)

    harness.project_workflow_directly("alpha")
    scene3_text_ids = harness.output_ids_for_scene_source(
        scene_key="scene3",
        source_key="alpha:text",
    )
    scene3_upscale_id = harness.output_ids_for_scene_source(
        scene_key="scene3",
        source_key="alpha:upscale",
    )[0]
    harness.wait_until(lambda: len(harness.fingerprint().grid_target_frames) == 3)
    scene_overview = harness.fingerprint()
    assert scene3_upscale_id in {
        placement[1] for placement in scene_overview.grid_target_frames
    }
    assert scene_overview.scene_selector_hidden is False
    canvas = harness.shell.output_canvas
    assert canvas.tabbar_container.isVisibleTo(canvas)
    assert canvas.scene_selector_button.isVisibleTo(canvas)
    assert not canvas.scene_selector_button.visibleRegion().isEmpty()

    harness.click_canvas_image(scene3_upscale_id)
    harness.wait_until(
        lambda: (
            {placement[1] for placement in harness.fingerprint().grid_target_frames}
            == set(scene3_text_ids)
        )
    )
    workflow = harness.shell.workflow_session_service.workflows["workflow-alpha"]
    batch_grid = harness.fingerprint()
    assert workflow.active_output_scene_key == "scene3"
    assert workflow.active_output_scene_overview is False
    assert workflow.active_output_source_key == "alpha:text"
    assert workflow.active_output_set_index == 0
    assert workflow.active_output_uuid is None
    assert batch_grid.active_composition_id is not None
    assert batch_grid.scene_selector_hidden is False
    assert batch_grid.set_selector_hidden is False
    assert canvas.scene_selector_button.isVisibleTo(canvas)
    assert canvas.set_selector_button.isVisibleTo(canvas)
    assert not canvas.scene_selector_button.visibleRegion().isEmpty()
    assert not canvas.set_selector_button.visibleRegion().isEmpty()

    harness.click_canvas_image(scene3_text_ids[1])
    harness.wait_until(
        lambda: harness.fingerprint().active_image_id == scene3_text_ids[1]
    )
    assert workflow.active_output_source_key == "alpha:text"
    assert workflow.active_output_set_index == 2
    assert workflow.active_output_uuid == scene3_text_ids[1]

    assert harness.output_set_picker_keys() == ("0", "1", "2", "3")
    harness.select_output_set(3)
    harness.wait_until(
        lambda: harness.fingerprint().active_image_id == scene3_text_ids[2]
    )
    assert workflow.active_output_set_index == 3
    assert workflow.active_output_uuid == scene3_text_ids[2]

    assert harness.output_set_picker_keys() == ("0", "1", "2", "3")
    harness.select_output_set(0)
    harness.wait_until(lambda: len(harness.fingerprint().grid_target_frames) == 3)
    grid_state = harness.fingerprint()
    assert workflow.active_output_source_key == "alpha:text"
    assert workflow.active_output_set_index == 0
    assert workflow.active_output_uuid is None
    assert grid_state.active_composition_id is not None
    assert {placement[1] for placement in grid_state.grid_target_frames} == set(
        scene3_text_ids
    )


def test_multi_source_grid_survives_workflow_switching(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Restore a source-grid composition after switching away and back."""

    harness.add_workflow("alpha", activate=True)
    harness.add_workflow("beta")
    alpha_run = harness.start_run("alpha")
    harness.emit_output(
        alpha_run,
        OutputSpec("alpha-left", "Alpha Left", (210, 40, 40)),
    )
    harness.emit_output(
        alpha_run,
        OutputSpec("alpha-right", "Alpha Right", (40, 210, 40)),
    )
    harness.wait_for_output_count("alpha", 2)
    harness.assert_scene_composition_for_workflow("alpha")

    harness.activate_workflow("beta")
    beta_run = harness.start_run("beta")
    harness.emit_output(
        beta_run,
        OutputSpec("beta-save", "Beta", (40, 40, 210)),
    )
    harness.wait_for_output_count("beta", 1)
    harness.assert_showing_workflow("beta", color=(40, 40, 210))

    harness.activate_workflow("alpha")
    harness.assert_scene_composition_for_workflow("alpha")
    harness.assert_not_showing_workflow("beta")


def test_source_grid_reflows_between_tall_and_wide_qpane_viewports(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """A live source grid should replace topology after a physical resize breakpoint."""

    harness.add_workflow("alpha", activate=True)
    run = harness.start_run("alpha")
    harness.emit_output(
        run,
        OutputSpec("shared", "Shared", (210, 40, 40), list_index=0),
    )
    harness.emit_output(
        run,
        OutputSpec("shared", "Shared", (40, 210, 40), list_index=1),
    )
    harness.wait_for_output_count("alpha", 2)
    workspace = harness.shell.output_canvas.workspace
    previous_snapshot = workspace.gridSnapshot()
    harness.set_output_viewport_extent(420.0, 1000.0)
    wait_for_new_grid_snapshot(harness, previous_snapshot)
    harness.wait_until(lambda: grid_dimensions(harness.fingerprint()) == (1, 2))
    tall = harness.fingerprint()
    previous_snapshot = workspace.gridSnapshot()
    harness.set_output_viewport_extent(1200.0, 420.0)
    wait_for_new_grid_snapshot(harness, previous_snapshot)
    harness.wait_until(lambda: grid_dimensions(harness.fingerprint()) == (2, 1))
    wide = harness.fingerprint()

    assert tall.active_composition_id == wide.active_composition_id
    assert [layer[0] for layer in tall.grid_target_frames] == [
        layer[0] for layer in wide.grid_target_frames
    ]

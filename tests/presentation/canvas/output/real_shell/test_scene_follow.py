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

"""Verify automatic scene and generation-session Output following."""

from __future__ import annotations

from tests.presentation.canvas.output.real_shell.synchronization import (
    wait_for_output_delivery,
)
from tests.support.real_output_canvas.harness import RealShellOutputCanvasHarness
from tests.support.real_output_canvas.models import OutputSpec, SceneSpec


def test_scene_batch_outputs_project_as_scene_composition(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Project a multi-image scene run as an Output scene composition."""

    harness.add_workflow("alpha", activate=True)
    run = harness.start_run("alpha")
    scene = SceneSpec(
        run_id="scene-run-alpha",
        key="scene-1",
        title="Scene 1",
        order=1,
        count=2,
    )

    harness.emit_output(
        run,
        OutputSpec(
            "alpha-left", "Alpha Left", (200, 30, 30), list_index=0, scene=scene
        ),
    )
    harness.emit_output(
        run,
        OutputSpec(
            "alpha-right",
            "Alpha Right",
            (30, 30, 200),
            list_index=1,
            scene=scene,
        ),
    )
    harness.wait_for_output_count("alpha", 2)
    harness.wait_until(lambda: harness.fingerprint().active_composition_id is not None)

    harness.assert_scene_composition_for_workflow("alpha")


def test_automatic_scene_follow_promotes_only_populated_views_and_honors_drilldown(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Follow the least-specific populated route until the user chooses a result."""

    harness.add_workflow("alpha", activate=True)
    harness.show_canvas("Output")
    first_scene = SceneSpec(
        run_id="scene-run-alpha",
        key="scene-1",
        title="Scene 1",
        order=0,
        count=2,
    )
    first_run = harness.start_run("alpha", run_index=1)
    first_colors = ((210, 40, 40), (40, 210, 40), (40, 40, 210))
    for batch_index, color in enumerate(first_colors):
        harness.emit_output(
            first_run,
            OutputSpec(
                "alpha:text",
                "Text to Image",
                color,
                batch_index=batch_index,
                scene=first_scene,
            ),
        )
    harness.wait_for_output_count("alpha", 3)
    harness.wait_until(lambda: len(harness.fingerprint().grid_target_frames) == 3)

    canvas = harness.shell.output_canvas
    first_only = harness.fingerprint()
    assert first_only.scene_selector_hidden is True
    assert first_only.set_selector_hidden is False
    harness.wait_until(lambda: canvas.set_selector_button.isVisibleTo(canvas))
    assert not canvas.scene_selector_button.isVisibleTo(canvas)
    assert canvas.set_selector_button.isVisibleTo(canvas)
    assert {item[1] for item in first_only.grid_target_frames} == set(
        harness.output_ids("alpha")
    )

    second_scene = SceneSpec(
        run_id="scene-run-alpha",
        key="scene-2",
        title="Scene 2",
        order=1,
        count=2,
    )
    second_run = harness.start_run("alpha", run_index=2)
    harness.emit_output(
        second_run,
        OutputSpec(
            "alpha:text",
            "Text to Image",
            (190, 120, 30),
            batch_index=0,
            scene=second_scene,
        ),
    )
    harness.wait_for_output_count("alpha", 4)
    harness.wait_until(lambda: len(harness.fingerprint().grid_target_frames) == 2)

    overview = harness.fingerprint()
    assert overview.scene_selector_hidden is False
    assert overview.set_selector_hidden is True
    harness.wait_until(lambda: canvas.scene_selector_button.isVisibleTo(canvas))
    assert canvas.scene_selector_button.isVisibleTo(canvas)
    assert not canvas.set_selector_button.isVisibleTo(canvas)
    first_scene_ids = harness.output_ids_for_scene_source(
        scene_key="scene-1",
        source_key="alpha:text",
    )
    harness.click_canvas_image(harness.output_representative_id_for_scene("scene-1"))
    harness.wait_until(lambda: len(harness.fingerprint().grid_target_frames) == 3)
    harness.click_canvas_image(first_scene_ids[1])
    harness.wait_until(
        lambda: harness.fingerprint().active_image_id == first_scene_ids[1]
    )
    selected = harness.fingerprint()
    assert selected.workflow_output_focus_modes["workflow-alpha"] == "manual"

    harness.emit_output(
        second_run,
        OutputSpec(
            "alpha:text",
            "Text to Image",
            (30, 120, 190),
            batch_index=1,
            scene=second_scene,
        ),
    )
    harness.wait_for_output_count("alpha", 5)
    harness.wait_until(
        lambda: (
            len(
                harness.output_ids_for_scene_source(
                    scene_key="scene-2",
                    source_key="alpha:text",
                )
            )
            == 2
        )
    )

    settled = harness.fingerprint()
    assert settled.active_image_id == first_scene_ids[1]
    assert settled.workflow_output_focus_modes["workflow-alpha"] == "manual"
    projection = canvas._output_projection
    assert projection is not None
    assert len(projection.scene_groups) == 2
    assert (
        len(
            harness.output_ids_for_scene_source(
                scene_key="scene-2",
                source_key="alpha:text",
            )
        )
        == 2
    )


def test_generation_session_follows_terminal_cube_then_honors_manual_navigation(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Follow terminal cube detail automatically until the user navigates."""

    harness.add_workflow("alpha", activate=True)
    harness.show_canvas("Output")
    baseline_run = harness.start_run("alpha", run_index=1)
    harness.emit_output(
        baseline_run,
        OutputSpec(
            "alpha:baseline",
            "Baseline",
            (80, 140, 200),
            batch_index=0,
        ),
    )
    harness.emit_output(
        baseline_run,
        OutputSpec(
            "alpha:baseline",
            "Baseline",
            (60, 120, 180),
            batch_index=1,
        ),
    )
    harness.wait_for_output_count("alpha", 2)
    harness.wait_until(lambda: len(harness.fingerprint().grid_target_frames) == 2)
    baseline_id = harness.output_ids("alpha")[1]
    harness.click_canvas_image(baseline_id)
    harness.wait_until(
        lambda: (
            harness.fingerprint().workflow_output_focus_modes["workflow-alpha"]
            == "manual"
        )
    )

    automatic_run = harness.start_run("alpha", run_index=2)
    harness.emit_output(
        automatic_run,
        OutputSpec(
            "alpha:draft",
            "Draft",
            (200, 70, 70),
            batch_index=0,
        ),
    )
    harness.emit_output(
        automatic_run,
        OutputSpec(
            "alpha:draft",
            "Draft",
            (170, 50, 50),
            batch_index=1,
        ),
    )
    harness.wait_for_output_count("alpha", 2)
    harness.wait_until(lambda: len(harness.fingerprint().grid_target_frames) == 2)
    draft_grid = harness.fingerprint()
    assert draft_grid.active_source_tab_key == "alpha:draft"
    assert draft_grid.workflow_output_focus_modes["workflow-alpha"] == "automatic"

    harness.emit_output(
        automatic_run,
        OutputSpec("alpha:upscale", "Upscale", (65, 185, 105)),
    )
    harness.wait_for_output_count("alpha", 3)
    harness.wait_until(
        lambda: harness.fingerprint().active_source_tab_key == "alpha:upscale"
    )
    harness.assert_showing_workflow("alpha", color=(65, 185, 105))

    harness.select_output_source("alpha:draft")
    harness.wait_until(
        lambda: harness.fingerprint().active_source_tab_key == "alpha:draft"
    )
    selected_draft = harness.fingerprint()
    assert selected_draft.workflow_output_focus_modes["workflow-alpha"] == "manual"
    harness.emit_output(
        automatic_run,
        OutputSpec("alpha:final", "Final", (70, 105, 220)),
    )
    harness.wait_for_output_count("alpha", 4)
    settled = harness.fingerprint()
    assert settled.active_source_tab_key == "alpha:draft"
    assert (
        settled.workflow_output_routes["workflow-alpha"]
        == (selected_draft.workflow_output_routes["workflow-alpha"])
    )

    next_run = harness.start_run("alpha", run_index=3)
    before_presentable = harness.fingerprint()
    assert before_presentable.active_source_tab_key == "alpha:draft"
    assert (
        before_presentable.workflow_output_routes["workflow-alpha"]
        == (selected_draft.workflow_output_routes["workflow-alpha"])
    )
    harness.emit_unloadable_output(
        next_run,
        OutputSpec("alpha:new-draft", "New Draft", (210, 90, 130)),
    )
    wait_for_output_delivery(harness)
    after_failure = harness.fingerprint()
    assert after_failure.active_source_tab_key == "alpha:draft"
    assert (
        after_failure.workflow_output_routes["workflow-alpha"]
        == (selected_draft.workflow_output_routes["workflow-alpha"])
    )

    harness.emit_output(
        next_run,
        OutputSpec("alpha:new-draft", "New Draft", (210, 130, 90)),
    )
    harness.wait_for_output_count("alpha", 1)
    harness.wait_until(
        lambda: harness.fingerprint().active_source_tab_key == "alpha:new-draft"
    )
    harness.emit_output(
        next_run,
        OutputSpec(
            "alpha:new-final",
            "New Final",
            (90, 170, 220),
            batch_index=0,
        ),
    )
    harness.emit_output(
        next_run,
        OutputSpec(
            "alpha:new-final",
            "New Final",
            (70, 145, 200),
            batch_index=1,
        ),
    )
    harness.wait_for_output_count("alpha", 3)
    harness.wait_until(lambda: len(harness.fingerprint().grid_target_frames) == 2)
    final_grid = harness.fingerprint()
    assert final_grid.active_source_tab_key == "alpha:new-final"
    assert final_grid.workflow_output_focus_modes["workflow-alpha"] == "automatic"

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

"""Verify Output state across workflow switching and hidden projection."""

from __future__ import annotations


from tests.support.real_output_canvas.harness import RealShellOutputCanvasHarness
from tests.support.real_output_canvas.models import OutputSpec, SceneSpec


def test_multi_scene_overview_survives_unrelated_workflow_output(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Keep an active scene overview routed after unrelated workflow output."""

    harness.add_workflow("alpha", activate=True)
    harness.add_workflow("beta")
    alpha_run = harness.start_run("alpha")
    first_scene = SceneSpec(
        run_id="scene-run-alpha",
        key="scene-1",
        title="Scene 1",
        order=1,
        count=2,
    )
    second_scene = SceneSpec(
        run_id="scene-run-alpha",
        key="scene-2",
        title="Scene 2",
        order=2,
        count=2,
    )
    harness.emit_output(
        alpha_run,
        OutputSpec("alpha-scene-1", "Alpha Scene 1", (200, 80, 30), scene=first_scene),
    )
    harness.emit_output(
        alpha_run,
        OutputSpec(
            "alpha-scene-2",
            "Alpha Scene 2",
            (30, 80, 200),
            scene=second_scene,
        ),
    )
    harness.wait_for_output_count("alpha", 2)
    harness.assert_scene_composition_for_workflow("alpha")
    canvas = harness.shell.output_canvas
    projection = canvas._output_projection
    assert projection is not None
    assert projection.scene_count == 2
    assert len(projection.scene_groups) == 2
    harness.wait_until(lambda: canvas.scene_selector_button.isVisibleTo(canvas))
    assert canvas.scene_selector_button.isVisibleTo(canvas)

    beta_run = harness.start_run("beta")
    harness.emit_output(
        beta_run,
        OutputSpec("beta-save", "Beta", (80, 200, 30)),
    )
    harness.wait_for_output_count("beta", 1)

    harness.assert_scene_composition_for_workflow("alpha")
    harness.assert_not_showing_workflow("beta")


def test_same_workflow_reselection_during_hidden_projection_still_displays_output(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Flush a pending same-workflow Output projection after canvas reselection."""

    harness.add_workflow("alpha", activate=True)
    harness.show_canvas("Input")
    run = harness.start_run("alpha")
    harness.emit_output(
        run,
        OutputSpec("alpha-save", "Alpha", (180, 110, 30)),
    )
    harness.wait_for_output_count("alpha", 1)
    harness.activate_workflow("alpha")

    harness.show_canvas("Output")

    harness.assert_showing_workflow("alpha", color=(180, 110, 30))


def test_hidden_output_with_unrelated_arrival_does_not_override_active_on_return(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Keep active workflow routing intact after hidden unrelated output arrives."""

    harness.add_workflow("alpha", activate=True)
    harness.add_workflow("beta")
    alpha_run = harness.start_run("alpha")
    harness.emit_output(
        alpha_run,
        OutputSpec("alpha-save", "Alpha", (95, 170, 30)),
    )
    harness.wait_for_output_count("alpha", 1)
    harness.assert_showing_workflow("alpha", color=(95, 170, 30))

    harness.show_canvas("Input")
    beta_run = harness.start_run("beta")
    harness.emit_output(
        beta_run,
        OutputSpec("beta-save", "Beta", (30, 95, 170)),
    )
    harness.wait_for_output_count("beta", 1)
    harness.show_canvas("Output")

    harness.assert_showing_workflow("alpha", color=(95, 170, 30))
    harness.assert_not_showing_workflow("beta")


def test_rapid_alternating_workflow_arrivals_preserve_selected_workflow(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Preserve selected workflow route during rapid A/B output arrivals."""

    harness.add_workflow("alpha", activate=True)
    harness.add_workflow("beta")
    alpha_first = harness.start_run("alpha", run_index=1)
    beta_first = harness.start_run("beta", run_index=1)
    alpha_second = harness.start_run("alpha", run_index=2)
    beta_second = harness.start_run("beta", run_index=2)

    harness.emit_output(
        alpha_first,
        OutputSpec("alpha-old", "Alpha Old", (80, 80, 80)),
    )
    harness.emit_output(
        beta_first,
        OutputSpec("beta-old", "Beta Old", (90, 90, 90)),
    )
    harness.emit_output(
        alpha_second,
        OutputSpec("alpha-new", "Alpha New", (190, 40, 70)),
    )
    harness.emit_output(
        beta_second,
        OutputSpec("beta-new", "Beta New", (40, 70, 190)),
    )
    harness.wait_for_output_count("alpha", 1)
    harness.wait_for_output_count("beta", 1)

    harness.assert_showing_workflow("alpha", color=(190, 40, 70))
    harness.assert_not_showing_workflow("beta")
    harness.activate_workflow("beta")
    harness.assert_showing_workflow("beta", color=(40, 70, 190))

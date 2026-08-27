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

"""Verify final Output visibility and active-workflow projection."""

from __future__ import annotations


from tests.support.real_output_canvas.harness import RealShellOutputCanvasHarness
from tests.support.real_output_canvas.models import OutputSpec


def test_active_workflow_final_output_displays_on_output_canvas(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Display a generated image for the selected workflow on the real workspace."""

    harness.add_workflow("alpha", activate=True)
    run = harness.start_run("alpha")

    harness.emit_output(
        run,
        OutputSpec(
            source_key="alpha-save",
            source_label="Alpha",
            color=(180, 20, 40),
        ),
    )
    harness.wait_for_output_count("alpha", 1)

    harness.assert_showing_workflow("alpha", color=(180, 20, 40))


def test_inactive_workflow_final_output_does_not_replace_active_output(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Keep the active workflow visible when another workflow receives output."""

    harness.add_workflow("alpha", activate=True)
    harness.add_workflow("beta")
    alpha_run = harness.start_run("alpha")
    harness.emit_output(
        alpha_run,
        OutputSpec("alpha-save", "Alpha", (20, 140, 60)),
    )
    harness.wait_for_output_count("alpha", 1)
    harness.assert_showing_workflow("alpha", color=(20, 140, 60))

    beta_run = harness.start_run("beta")
    harness.emit_output(
        beta_run,
        OutputSpec("beta-save", "Beta", (80, 30, 190)),
    )
    harness.wait_for_output_count("beta", 1)

    harness.assert_showing_workflow("alpha", color=(20, 140, 60))
    harness.assert_not_showing_workflow("beta")
    harness.activate_workflow("beta")
    harness.assert_showing_workflow("beta", color=(80, 30, 190))


def test_output_arriving_during_switch_projects_only_new_active_workflow(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Display an output that commits after its workflow becomes active."""

    harness.add_workflow("alpha", activate=True)
    harness.add_workflow("beta")
    beta_run = harness.start_run("beta")

    harness.emit_output(
        beta_run,
        OutputSpec("beta-save", "Beta", (30, 70, 210)),
    )
    harness.activate_workflow("beta")
    harness.wait_for_output_count("beta", 1)

    harness.assert_showing_workflow("beta", color=(30, 70, 210))
    harness.assert_not_showing_workflow("alpha")


def test_foreign_output_arriving_during_switch_does_not_clear_new_active_canvas(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Do not let a late inactive-workflow output clear the selected workflow."""

    harness.add_workflow("alpha", activate=True)
    harness.add_workflow("beta")
    beta_run = harness.start_run("beta")
    harness.activate_workflow("beta")
    harness.emit_output(
        beta_run,
        OutputSpec("beta-save", "Beta", (25, 160, 220)),
    )
    harness.wait_for_output_count("beta", 1)
    harness.assert_showing_workflow("beta", color=(25, 160, 220))

    alpha_run = harness.start_run("alpha")
    harness.emit_output(
        alpha_run,
        OutputSpec("alpha-save", "Alpha", (210, 70, 20)),
    )
    harness.wait_for_output_count("alpha", 1)

    harness.assert_showing_workflow("beta", color=(25, 160, 220))
    harness.assert_not_showing_workflow("alpha")


def test_active_output_generated_while_output_canvas_hidden_projects_when_reselected(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Defer hidden Output projection and display it when Output is selected."""

    harness.add_workflow("alpha", activate=True)
    harness.show_canvas("Input")
    run = harness.start_run("alpha")

    harness.emit_output(
        run,
        OutputSpec("alpha-save", "Alpha", (150, 90, 25)),
    )
    harness.wait_for_output_count("alpha", 1)
    state_while_hidden = harness.fingerprint()
    assert not state_while_hidden.active_canvas_visible

    harness.show_canvas("Output")
    harness.wait_until(lambda: not harness.fingerprint().active_image_is_null)

    harness.assert_showing_workflow("alpha", color=(150, 90, 25))


def test_batch_navigation_is_visible_when_output_opens_after_hidden_generation(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Reveal batch navigation after a multi-batch projection completed offscreen."""

    harness.add_workflow("alpha", activate=True)
    harness.show_canvas("Input")
    run = harness.start_run("alpha")
    harness.emit_output(
        run,
        OutputSpec(
            "alpha-batch",
            "Alpha Batch",
            (150, 90, 25),
            list_index=0,
            batch_index=0,
        ),
    )
    harness.emit_output(
        run,
        OutputSpec(
            "alpha-batch",
            "Alpha Batch",
            (25, 90, 150),
            list_index=0,
            batch_index=1,
        ),
    )
    harness.wait_for_output_count("alpha", 2)

    harness.show_canvas("Output")
    canvas = harness.shell.output_canvas
    harness.wait_until(lambda: canvas.set_selector_button.isVisibleTo(canvas))

    assert canvas.set_count == 2
    assert canvas.set_selector_button.isVisibleTo(canvas)
    assert not canvas.set_selector_button.visibleRegion().isEmpty()

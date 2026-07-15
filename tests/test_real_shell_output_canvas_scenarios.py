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

"""Exercise Output canvas behavior through the real shell composition path."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF

import os
from collections.abc import Iterator
from typing import Any, cast

import pytest

from tests.support.real_output_canvas.harness import RealShellOutputCanvasHarness
from tests.support.real_output_canvas.models import (
    OutputSpec,
    SceneSpec,
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "real Output QPane shell harness requires non-xdist execution on Windows",
        allow_module_level=True,
    )


@pytest.fixture
def harness() -> Iterator[RealShellOutputCanvasHarness]:
    """Create and close a real-shell Output canvas harness."""

    shell_harness = RealShellOutputCanvasHarness()
    try:
        yield shell_harness
    finally:
        shell_harness.close()


def test_active_workflow_final_output_displays_on_output_canvas(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Display a generated image for the selected workflow on the real QPane."""

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
    harness.wait_until(lambda: not harness.fingerprint().current_image_is_null)

    harness.assert_showing_workflow("alpha", color=(150, 90, 25))


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
    harness.wait_until(
        lambda: harness.fingerprint().pane_current_composition_id is not None
    )

    harness.assert_scene_composition_for_workflow("alpha")


def test_stale_final_after_newer_run_does_not_register_or_display(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Reject a final output from a run superseded by a newer run."""

    harness.add_workflow("alpha", activate=True)
    stale_run = harness.start_run("alpha", run_index=1)
    harness.start_run("alpha", run_index=2)

    harness.emit_output(
        stale_run,
        OutputSpec("alpha-stale", "Alpha Stale", (220, 20, 20)),
    )
    harness.drain_events_for(200)

    assert harness.output_count("alpha") == 0
    state = harness.fingerprint()
    assert state.pane_current_image_id is None
    assert state.pane_current_composition_id is None


def test_preview_final_interleaving_retires_preview_and_displays_final(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Retire a matching live preview when the final output arrives."""

    harness.add_workflow("alpha", activate=True)
    baseline_run = harness.start_run("alpha", run_index=1)
    harness.emit_output(
        baseline_run,
        OutputSpec("alpha-save", "Alpha", (30, 30, 30)),
    )
    harness.wait_for_output_count("alpha", 1)
    run = harness.start_run("alpha", run_index=2)

    harness.emit_preview(
        run,
        OutputSpec("alpha-save", "Alpha", (60, 130, 210)),
    )
    harness.wait_for_preview_count(1)
    harness.assert_preview_displayed(color=(60, 130, 210))

    harness.emit_output(
        run,
        OutputSpec("alpha-save", "Alpha", (210, 130, 60)),
    )
    harness.wait_for_output_count("alpha", 2)
    harness.wait_until(lambda: harness.preview_count() == 0)

    harness.assert_no_previews()
    harness.assert_showing_workflow("alpha", color=(210, 130, 60))


def test_stale_preview_after_newer_run_does_not_register_or_display(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Reject a preview from a run superseded by a newer run."""

    harness.add_workflow("alpha", activate=True)
    baseline_run = harness.start_run("alpha", run_index=1)
    harness.emit_output(
        baseline_run,
        OutputSpec("alpha-save", "Alpha", (30, 30, 30)),
    )
    harness.wait_for_output_count("alpha", 1)
    stale_run = harness.start_run("alpha", run_index=2)
    harness.start_run("alpha", run_index=3)

    harness.emit_preview(
        stale_run,
        OutputSpec("alpha-save", "Alpha", (220, 20, 160)),
    )
    harness.drain_events_for(200)

    harness.assert_no_previews()
    harness.assert_showing_workflow("alpha", color=(30, 30, 30))


def test_final_after_completed_run_registers_and_displays(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Allow a final output callback that arrives after listener completion."""

    harness.add_workflow("alpha", activate=True)
    run = harness.start_run("alpha")
    harness.complete_run(run)

    harness.emit_output(
        run,
        OutputSpec("alpha-save", "Alpha", (40, 190, 120)),
    )
    harness.wait_for_output_count("alpha", 1)

    harness.assert_showing_workflow("alpha", color=(40, 190, 120))


def test_preview_after_completed_run_does_not_register_or_display(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Reject a preview callback that arrives after listener completion."""

    harness.add_workflow("alpha", activate=True)
    baseline_run = harness.start_run("alpha", run_index=1)
    harness.emit_output(
        baseline_run,
        OutputSpec("alpha-save", "Alpha", (30, 30, 30)),
    )
    harness.wait_for_output_count("alpha", 1)
    run = harness.start_run("alpha", run_index=2)
    harness.complete_run(run)

    harness.emit_preview(
        run,
        OutputSpec("alpha-save", "Alpha", (120, 40, 190)),
    )
    harness.drain_events_for(200)

    harness.assert_no_previews()
    harness.assert_showing_workflow("alpha", color=(30, 30, 30))


def test_repeated_source_previews_replace_visible_preview_lane(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Keep only the newest preview visible for one active source lane."""

    harness.add_workflow("alpha", activate=True)
    baseline_run = harness.start_run("alpha", run_index=1)
    harness.emit_output(
        baseline_run,
        OutputSpec("alpha-save", "Alpha", (30, 30, 30)),
    )
    harness.wait_for_output_count("alpha", 1)
    run = harness.start_run("alpha", run_index=2)

    harness.emit_preview(
        run,
        OutputSpec("alpha-save", "Alpha", (20, 90, 180)),
    )
    harness.wait_for_preview_count(1)
    harness.assert_preview_displayed(color=(20, 90, 180))

    harness.emit_preview(
        run,
        OutputSpec("alpha-save", "Alpha", (180, 90, 20)),
    )
    harness.wait_for_preview_count(1)

    harness.assert_preview_displayed(color=(180, 90, 20))


def test_inactive_workflow_preview_does_not_replace_active_preview(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Reject inactive-workflow previews even when they target a valid source."""

    harness.add_workflow("alpha", activate=True)
    harness.add_workflow("beta")
    alpha_baseline = harness.start_run("alpha", run_index=1)
    harness.emit_output(
        alpha_baseline,
        OutputSpec("alpha-save", "Alpha", (30, 30, 30)),
    )
    harness.wait_for_output_count("alpha", 1)
    beta_baseline = harness.start_run("beta", run_index=1)
    harness.emit_output(
        beta_baseline,
        OutputSpec("beta-save", "Beta", (50, 50, 50)),
    )
    harness.wait_for_output_count("beta", 1)
    alpha_run = harness.start_run("alpha", run_index=2)
    harness.emit_preview(
        alpha_run,
        OutputSpec("alpha-save", "Alpha", (40, 160, 210)),
    )
    harness.wait_for_preview_count(1)
    harness.assert_preview_displayed(color=(40, 160, 210))
    beta_run = harness.start_run("beta", run_index=2)

    harness.emit_preview(
        beta_run,
        OutputSpec("beta-save", "Beta", (210, 160, 40)),
    )
    harness.drain_events_for(200)

    harness.wait_for_preview_count(1)
    harness.assert_preview_displayed(color=(40, 160, 210))
    harness.assert_not_showing_workflow("beta")


def test_hidden_output_unrelated_final_does_not_clear_active_preview(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Preserve an active preview across hidden unrelated workflow output."""

    harness.add_workflow("alpha", activate=True)
    harness.add_workflow("beta")
    alpha_baseline = harness.start_run("alpha", run_index=1)
    harness.emit_output(
        alpha_baseline,
        OutputSpec("alpha-save", "Alpha", (30, 30, 30)),
    )
    harness.wait_for_output_count("alpha", 1)
    alpha_run = harness.start_run("alpha", run_index=2)
    harness.emit_preview(
        alpha_run,
        OutputSpec("alpha-save", "Alpha", (70, 170, 220)),
    )
    harness.wait_for_preview_count(1)
    harness.assert_preview_displayed(color=(70, 170, 220))

    harness.show_canvas("Input")
    beta_run = harness.start_run("beta")
    harness.emit_output(
        beta_run,
        OutputSpec("beta-save", "Beta", (220, 170, 70)),
    )
    harness.wait_for_output_count("beta", 1)
    harness.show_canvas("Output")

    harness.wait_for_preview_count(1)
    harness.assert_preview_displayed(color=(70, 170, 220))
    harness.assert_not_showing_workflow("beta")


def test_nonmatching_final_does_not_retire_source_preview_lane(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """A final from a different source should display without retiring the preview."""

    harness.add_workflow("alpha", activate=True)
    baseline_run = harness.start_run("alpha", run_index=1)
    harness.emit_output(
        baseline_run,
        OutputSpec("alpha-save", "Alpha", (30, 30, 30)),
    )
    harness.wait_for_output_count("alpha", 1)
    run = harness.start_run("alpha", run_index=2)
    harness.emit_preview(
        run,
        OutputSpec("alpha-save", "Alpha", (60, 130, 210)),
    )
    harness.wait_for_preview_count(1)
    harness.assert_preview_displayed(color=(60, 130, 210))

    harness.emit_output(
        run,
        OutputSpec("alpha-other", "Alpha Other", (210, 60, 130)),
    )
    harness.wait_for_output_count("alpha", 2)

    harness.wait_for_preview_count(1)
    harness.assert_showing_workflow("alpha", color=(210, 60, 130))


def test_pending_preview_during_workflow_switch_cannot_hijack_new_active_route(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """A queued preview must be authorized against the workflow active at flush."""

    harness.add_workflow("alpha", activate=True)
    harness.add_workflow("beta")
    alpha_baseline = harness.start_run("alpha", run_index=1)
    harness.emit_output(
        alpha_baseline,
        OutputSpec("alpha-save", "Alpha", (30, 30, 30)),
    )
    harness.wait_for_output_count("alpha", 1)
    beta_baseline = harness.start_run("beta", run_index=1)
    harness.emit_output(
        beta_baseline,
        OutputSpec("beta-save", "Beta", (70, 70, 200)),
    )
    harness.wait_for_output_count("beta", 1)
    harness.assert_showing_workflow("alpha", color=(30, 30, 30))
    alpha_run = harness.start_run("alpha", run_index=2)

    harness.emit_preview(
        alpha_run,
        OutputSpec("alpha-save", "Alpha", (220, 80, 30)),
    )
    harness.activate_workflow("beta")
    harness.drain_events_for(200)

    harness.assert_no_previews()
    harness.assert_showing_workflow("beta", color=(70, 70, 200))
    harness.assert_not_showing_workflow("alpha")


def test_same_workflow_reactivation_does_not_replay_final_over_preview(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Duplicate workflow activation must not replace a live preview with final."""

    harness.add_workflow("alpha", activate=True)
    baseline_run = harness.start_run("alpha", run_index=1)
    harness.emit_output(
        baseline_run,
        OutputSpec("alpha-save", "Alpha", (30, 30, 30)),
    )
    harness.wait_for_output_count("alpha", 1)
    run = harness.start_run("alpha", run_index=2)
    harness.emit_preview(
        run,
        OutputSpec("alpha-save", "Alpha", (30, 180, 220)),
    )
    harness.wait_for_preview_count(1)
    harness.assert_preview_displayed(color=(30, 180, 220))

    harness.activate_workflow("alpha")
    harness.project_workflow_directly("alpha")

    harness.wait_for_preview_count(1)
    harness.assert_preview_displayed(color=(30, 180, 220))


def test_pending_final_after_switch_away_registers_without_hijacking_active_route(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """A queued final from a previous workflow must not display after switching."""

    harness.add_workflow("alpha", activate=True)
    harness.add_workflow("beta")
    beta_baseline = harness.start_run("beta", run_index=1)
    harness.emit_output(
        beta_baseline,
        OutputSpec("beta-save", "Beta", (60, 80, 210)),
    )
    harness.wait_for_output_count("beta", 1)
    harness.activate_workflow("alpha")
    alpha_run = harness.start_run("alpha")

    harness.emit_output(
        alpha_run,
        OutputSpec("alpha-save", "Alpha", (210, 80, 60)),
    )
    harness.activate_workflow("beta")
    harness.wait_for_output_count("alpha", 1)

    harness.assert_showing_workflow("beta", color=(60, 80, 210))
    harness.assert_not_showing_workflow("alpha")


def test_manual_output_selection_survives_new_final_arrival(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """A user-selected older output should not be overwritten by new finals."""

    harness.add_workflow("alpha", activate=True)
    first_run = harness.start_run("alpha", run_index=1)
    harness.emit_output(
        first_run,
        OutputSpec("alpha-save", "Alpha", (40, 120, 200), list_index=0),
    )
    harness.wait_for_output_count("alpha", 1)
    second_run = harness.start_run("alpha", run_index=2)
    harness.emit_output(
        second_run,
        OutputSpec("alpha-save", "Alpha", (200, 120, 40), list_index=1),
    )
    harness.wait_for_output_count("alpha", 2)
    first_output_id = harness.output_ids("alpha")[0]

    harness.select_output_id(first_output_id)
    harness.assert_showing_workflow("alpha", color=(40, 120, 200))
    third_run = harness.start_run("alpha", run_index=3)
    harness.emit_output(
        third_run,
        OutputSpec("alpha-save", "Alpha", (120, 200, 40), list_index=2),
    )
    harness.wait_for_output_count("alpha", 3)

    harness.assert_showing_workflow("alpha", color=(40, 120, 200))


def test_pending_final_does_not_override_manual_reselection(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """A pending generated projection should not beat immediate user selection."""

    harness.add_workflow("alpha", activate=True)
    first_run = harness.start_run("alpha", run_index=1)
    harness.emit_output(
        first_run,
        OutputSpec("alpha-save", "Alpha", (45, 125, 205)),
    )
    harness.wait_for_output_count("alpha", 1)
    first_output_id = harness.output_ids("alpha")[0]
    second_run = harness.start_run("alpha", run_index=2)

    harness.emit_output(
        second_run,
        OutputSpec("alpha-save", "Alpha", (205, 125, 45)),
    )
    harness.select_output_id(first_output_id)
    harness.wait_for_output_count("alpha", 2)

    harness.assert_showing_workflow("alpha", color=(45, 125, 205))


def test_clear_active_output_with_visible_preview_removes_preview_and_route(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Clearing active Output must remove final state and transient previews."""

    harness.add_workflow("alpha", activate=True)
    baseline_run = harness.start_run("alpha", run_index=1)
    harness.emit_output(
        baseline_run,
        OutputSpec("alpha-save", "Alpha", (30, 30, 30)),
    )
    harness.wait_for_output_count("alpha", 1)
    run = harness.start_run("alpha", run_index=2)
    harness.emit_preview(
        run,
        OutputSpec("alpha-save", "Alpha", (90, 170, 230)),
    )
    harness.wait_for_preview_count(1)
    harness.assert_preview_displayed(color=(90, 170, 230))

    harness.clear_output_for("alpha")
    harness.wait_until(lambda: harness.output_count("alpha") == 0)
    harness.wait_until(lambda: harness.preview_count() == 0)

    state = harness.fingerprint()
    assert state.pane_current_image_id is None, state
    assert state.pane_current_composition_id is None, state
    assert state.current_image_is_null, state


def test_clearing_inactive_workflow_does_not_clear_active_output_or_preview(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Clearing an inactive workflow must not mutate active workflow visuals."""

    harness.add_workflow("alpha", activate=True)
    harness.add_workflow("beta")
    alpha_baseline = harness.start_run("alpha", run_index=1)
    harness.emit_output(
        alpha_baseline,
        OutputSpec("alpha-save", "Alpha", (30, 30, 30)),
    )
    harness.wait_for_output_count("alpha", 1)
    beta_run = harness.start_run("beta")
    harness.emit_output(
        beta_run,
        OutputSpec("beta-save", "Beta", (210, 80, 40)),
    )
    harness.wait_for_output_count("beta", 1)
    alpha_run = harness.start_run("alpha", run_index=2)
    harness.emit_preview(
        alpha_run,
        OutputSpec("alpha-save", "Alpha", (40, 160, 210)),
    )
    harness.wait_for_preview_count(1)
    harness.assert_preview_displayed(color=(40, 160, 210))

    harness.clear_output_for("beta")
    harness.wait_until(lambda: harness.output_count("beta") == 0)

    harness.wait_for_preview_count(1)
    harness.assert_preview_displayed(color=(40, 160, 210))
    harness.assert_not_showing_workflow("beta")


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
    harness.shell.output_canvas.activeOutputGridChanged.emit("shared")
    harness.process_events(cycles=8)

    pane = harness.shell.output_canvas.pane
    harness.set_output_viewport_extent(420.0, 1000.0)
    harness.wait_until(lambda: _grid_dimensions(harness.fingerprint()) == (1, 2))
    tall = harness.fingerprint()
    target_image_id = tall.scene_layer_placements[0][1]
    tall_hit = _scene_hit_for_image(pane, target_image_id)

    harness.set_output_viewport_extent(1200.0, 420.0)
    harness.wait_until(lambda: _grid_dimensions(harness.fingerprint()) == (2, 1))
    wide = harness.fingerprint()
    wide_hit = _scene_hit_for_image(pane, target_image_id)

    assert tall.pane_current_composition_id == wide.pane_current_composition_id
    assert [layer[0] for layer in tall.scene_layer_placements] == [
        layer[0] for layer in wide.scene_layer_placements
    ]
    assert tall_hit is not None
    assert wide_hit is not None
    assert tall_hit.layer_id == wide_hit.layer_id
    assert dict(tall_hit.metadata) == dict(wide_hit.metadata)


def _grid_dimensions(fingerprint: object) -> tuple[int, int] | None:
    """Infer grid columns and rows from fingerprinted layer placements."""

    placements = getattr(fingerprint, "scene_layer_placements", ())
    if not placements:
        return None
    columns = len({round(layer[2], 6) for layer in placements})
    rows = len({round(layer[3], 6) for layer in placements})
    return columns, rows


def _scene_hit_for_image(pane: object, image_id: object) -> Any | None:
    """Find one public scene hit for an image by scanning the physical panel."""

    hit_test = getattr(pane, "sceneHitTest", None)
    if not callable(hit_test):
        return None
    width = int(getattr(pane, "width")())
    height = int(getattr(pane, "height")())
    for y in range(4, height, 8):
        for x in range(4, width, 8):
            hit = hit_test(QPoint(x, y))
            if getattr(hit, "image_id", None) == image_id:
                return cast(Any, hit)
    return None


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
    observed: list[tuple[int, int] | None] = []
    for width, height in ((1400.0, 450.0), (800.0, 800.0), (450.0, 1400.0)):
        harness.set_output_viewport_extent(width, height)
        observed.append(_grid_dimensions(harness.fingerprint()))

    assert observed[0] != observed[-1]
    assert all(
        dimensions is not None and dimensions[0] * dimensions[1] >= 5
        for dimensions in observed
    )


def test_pending_grid_resize_cannot_replace_new_workflow_route(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Switching workflows before timer delivery should invalidate old grid work."""

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
    pane = harness.shell.output_canvas.pane
    pane.viewportRectChanged.emit(QRectF(0.0, 0.0, 1400.0, 420.0))

    harness.activate_workflow("beta")
    harness.drain_events_for(40)

    harness.assert_showing_workflow("beta", color=(30, 30, 210))
    harness.assert_not_showing_workflow("alpha")


def test_compare_route_ignores_grid_resize_delivery(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Viewport changes must not replace an active QPane comparison route."""

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
    harness.wait_until(
        lambda: harness.fingerprint().pane_current_image_id == first_image_id
    )
    canvas._runtime.compare.controller.set_compare_mode_enabled(True)
    harness.process_events(cycles=8)
    before = harness.fingerprint().pane_current_composition_id

    canvas.pane.viewportRectChanged.emit(QRectF(0.0, 0.0, 400.0, 1200.0))
    harness.drain_events_for(40)

    assert canvas._runtime.compare.controller.visible_compare_state().enabled is True
    assert harness.fingerprint().pane_current_composition_id == before


def test_scene_preview_to_final_during_resize_keeps_final_grid_content(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """A final should replace its live scene tile while resize work is pending."""

    harness.add_workflow("alpha", activate=True)
    run = harness.start_run("alpha")
    first_scene = SceneSpec("scene-run", "scene-1", "Scene 1", 0, 2)
    second_scene = SceneSpec("scene-run", "scene-2", "Scene 2", 1, 2)
    harness.emit_output(
        run,
        OutputSpec("scene-one", "Scene One", (190, 50, 40), scene=first_scene),
    )
    harness.emit_output(
        run,
        OutputSpec(
            "scene-one",
            "Scene One",
            (40, 50, 120),
            list_index=1,
            scene=second_scene,
        ),
    )
    harness.wait_for_output_count("alpha", 2)
    preview_run = harness.start_run("alpha", run_index=2)
    harness.emit_preview(
        preview_run,
        OutputSpec(
            "scene-one",
            "Scene One",
            (40, 190, 50),
            list_index=1,
            scene=second_scene,
        ),
    )
    harness.wait_for_preview_count(1)
    pane = harness.shell.output_canvas.pane
    pane.viewportRectChanged.emit(QRectF(0.0, 0.0, 420.0, 1000.0))
    harness.wait_until(lambda: len(harness.fingerprint().scene_layer_placements) == 2)
    preview_grid = harness.fingerprint()
    assert set(preview_grid.preview_image_ids).intersection(
        placement[1] for placement in preview_grid.scene_layer_placements
    )

    pane.viewportRectChanged.emit(QRectF(0.0, 0.0, 1200.0, 420.0))
    harness.emit_output(
        preview_run,
        OutputSpec(
            "scene-one",
            "Scene One",
            (40, 50, 190),
            list_index=1,
            scene=second_scene,
        ),
    )
    harness.wait_for_output_count("alpha", 3)
    harness.wait_for_preview_count(0)
    pane.viewportRectChanged.emit(QRectF(0.0, 0.0, 1200.0, 420.0))
    harness.wait_until(lambda: len(harness.fingerprint().scene_layer_placements) == 2)
    final_grid = harness.fingerprint()

    final_image_ids = {placement[1] for placement in final_grid.scene_layer_placements}
    assert final_image_ids <= set(harness.output_ids("alpha"))
    assert not set(preview_grid.preview_image_ids).intersection(final_image_ids)


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


def test_pending_final_for_closed_active_workflow_cannot_hijack_successor(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Reject a queued final callback after its active workflow has been closed."""

    harness.add_workflow("alpha", activate=True)
    harness.add_workflow("beta")
    beta_run = harness.start_run("beta")
    harness.emit_output(
        beta_run,
        OutputSpec("beta-save", "Beta", (30, 150, 210)),
    )
    harness.wait_for_output_count("beta", 1)
    harness.activate_workflow("alpha")
    alpha_run = harness.start_run("alpha")

    harness.emit_output(
        alpha_run,
        OutputSpec("alpha-save", "Alpha", (210, 80, 30)),
    )
    harness.close_workflow("alpha")
    harness.drain_events_for(300)

    state = harness.fingerprint()
    assert "workflow-alpha" not in state.workflow_output_image_ids, state
    assert state.pending_commit_count == 0, state
    assert "workflow-alpha" not in state.pending_projection_workflows, state
    harness.assert_showing_workflow("beta", color=(30, 150, 210))


def test_pending_final_for_closed_inactive_workflow_cannot_mutate_active_route(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Reject a queued final callback after its inactive workflow has been closed."""

    harness.add_workflow("alpha", activate=True)
    harness.add_workflow("beta")
    alpha_run = harness.start_run("alpha")
    harness.emit_output(
        alpha_run,
        OutputSpec("alpha-save", "Alpha", (95, 175, 45)),
    )
    harness.wait_for_output_count("alpha", 1)
    beta_run = harness.start_run("beta")

    harness.emit_output(
        beta_run,
        OutputSpec("beta-save", "Beta", (180, 65, 210)),
    )
    harness.close_workflow("beta")
    harness.drain_events_for(300)

    state = harness.fingerprint()
    assert "workflow-beta" not in state.workflow_output_image_ids, state
    assert state.pending_commit_count == 0, state
    assert "workflow-beta" not in state.pending_projection_workflows, state
    harness.assert_showing_workflow("alpha", color=(95, 175, 45))


def test_closing_workflow_with_visible_preview_clears_preview_and_restores_successor(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Closing a preview-owning workflow must not leave its preview on Output."""

    harness.add_workflow("alpha", activate=True)
    harness.add_workflow("beta")
    alpha_baseline = harness.start_run("alpha", run_index=1)
    harness.emit_output(
        alpha_baseline,
        OutputSpec("alpha-save", "Alpha", (30, 30, 30)),
    )
    harness.wait_for_output_count("alpha", 1)
    beta_run = harness.start_run("beta")
    harness.emit_output(
        beta_run,
        OutputSpec("beta-save", "Beta", (45, 155, 215)),
    )
    harness.wait_for_output_count("beta", 1)
    alpha_run = harness.start_run("alpha", run_index=2)
    harness.emit_preview(
        alpha_run,
        OutputSpec("alpha-save", "Alpha", (210, 120, 35)),
    )
    harness.wait_for_preview_count(1)
    harness.assert_preview_displayed(color=(210, 120, 35))

    harness.close_workflow("alpha")
    harness.drain_events_for(200)

    harness.assert_no_previews()
    harness.assert_showing_workflow("beta", color=(45, 155, 215))


def test_unloadable_final_output_does_not_clear_existing_active_canvas(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """A final callback whose image cannot load must not blank current Output."""

    harness.add_workflow("alpha", activate=True)
    baseline_run = harness.start_run("alpha", run_index=1)
    harness.emit_output(
        baseline_run,
        OutputSpec("alpha-save", "Alpha", (80, 160, 220)),
    )
    harness.wait_for_output_count("alpha", 1)
    failing_run = harness.start_run("alpha", run_index=2)

    harness.emit_unloadable_output(
        failing_run,
        OutputSpec("alpha-save", "Alpha", (220, 80, 160)),
    )
    harness.drain_events_for(300)

    assert harness.output_count("alpha") == 1
    assert len(harness.shell.error_reports) == 1
    harness.assert_showing_workflow("alpha", color=(80, 160, 220))


def test_invalid_live_final_identity_does_not_clear_existing_active_canvas(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Reject malformed live final identity without mutating visible Output."""

    harness.add_workflow("alpha", activate=True)
    baseline_run = harness.start_run("alpha", run_index=1)
    harness.emit_output(
        baseline_run,
        OutputSpec("alpha-save", "Alpha", (60, 145, 205)),
    )
    harness.wait_for_output_count("alpha", 1)
    invalid_run = harness.start_run("alpha", run_index=2)

    harness.emit_output(
        invalid_run,
        OutputSpec("", "", (205, 60, 145), list_index=0),
    )
    harness.drain_events_for(300)

    assert harness.output_count("alpha") == 1
    harness.assert_showing_workflow("alpha", color=(60, 145, 205))


def test_hidden_pending_projection_for_closed_workflow_is_pruned(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Do not retain hidden generated projections for workflows after close."""

    harness.add_workflow("alpha", activate=True)
    harness.add_workflow("beta")
    beta_run = harness.start_run("beta")
    harness.emit_output(
        beta_run,
        OutputSpec("beta-save", "Beta", (35, 135, 215)),
    )
    harness.wait_for_output_count("beta", 1)
    harness.activate_workflow("alpha")
    harness.show_canvas("Input")
    alpha_run = harness.start_run("alpha")
    harness.emit_output(
        alpha_run,
        OutputSpec("alpha-save", "Alpha", (215, 95, 35)),
    )
    harness.wait_for_output_count("alpha", 1)
    hidden_state = harness.fingerprint()
    assert "workflow-alpha" in hidden_state.pending_projection_workflows, hidden_state

    harness.close_workflow("alpha")
    harness.show_canvas("Output")
    harness.drain_events_for(300)

    state = harness.fingerprint()
    assert "workflow-alpha" not in state.workflow_output_image_ids, state
    assert "workflow-alpha" not in state.pending_projection_workflows, state
    harness.assert_showing_workflow("beta", color=(35, 135, 215))


def test_hidden_pending_projection_for_cleared_workflow_is_pruned(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Clearing Output should remove stale generated projection work."""

    harness.add_workflow("alpha", activate=True)
    baseline_run = harness.start_run("alpha", run_index=1)
    harness.emit_output(
        baseline_run,
        OutputSpec("alpha-save", "Alpha", (70, 150, 210)),
    )
    harness.wait_for_output_count("alpha", 1)
    harness.show_canvas("Input")
    generated_run = harness.start_run("alpha", run_index=2)
    harness.emit_output(
        generated_run,
        OutputSpec("alpha-save", "Alpha", (210, 90, 70)),
    )
    harness.wait_for_output_count("alpha", 2)
    hidden_state = harness.fingerprint()
    assert "workflow-alpha" in hidden_state.pending_projection_workflows, hidden_state

    harness.clear_output_for("alpha")
    harness.drain_events_for(200)

    state = harness.fingerprint()
    assert harness.output_count("alpha") == 0
    assert "workflow-alpha" not in state.pending_projection_workflows, state


def test_hidden_pending_projection_rekeys_when_workflow_is_renamed(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Renaming a workflow should not leave pending projections on old IDs."""

    harness.add_workflow("alpha", activate=True)
    harness.show_canvas("Input")
    run = harness.start_run("alpha")
    harness.emit_output(
        run,
        OutputSpec("alpha-save", "Alpha", (75, 155, 215)),
    )
    harness.wait_for_output_count("alpha", 1)
    hidden_state = harness.fingerprint()
    assert "workflow-alpha" in hidden_state.pending_projection_workflows, hidden_state

    harness.rename_workflow("alpha", "renamed-alpha")
    harness.show_canvas("Output")
    harness.drain_events_for(300)

    state = harness.fingerprint()
    assert "workflow-alpha" not in state.workflow_output_image_ids, state
    assert "workflow-alpha" not in state.pending_projection_workflows, state
    harness.assert_showing_workflow("renamed-alpha", color=(75, 155, 215))

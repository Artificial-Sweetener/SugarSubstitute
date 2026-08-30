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

"""Verify preview and final routing through workflow and manual selection changes."""

from __future__ import annotations

from tests.presentation.canvas.output.real_shell.synchronization import (
    wait_for_output_delivery,
)
from tests.support.real_output_canvas.harness import RealShellOutputCanvasHarness
from tests.support.real_output_canvas.models import OutputSpec


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
    wait_for_output_delivery(harness)

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
    run = harness.start_run("alpha", run_index=1)
    harness.emit_output(
        run,
        OutputSpec("alpha-save", "Alpha", (40, 120, 200), batch_index=0),
    )
    harness.wait_for_output_count("alpha", 1)
    harness.emit_output(
        run,
        OutputSpec("alpha-save", "Alpha", (200, 120, 40), batch_index=1),
    )
    harness.wait_for_output_count("alpha", 2)
    first_output_id = harness.output_ids("alpha")[0]

    harness.select_output_id(first_output_id)
    harness.assert_showing_workflow("alpha", color=(40, 120, 200))
    harness.emit_output(
        run,
        OutputSpec("alpha-save", "Alpha", (120, 200, 40), batch_index=2),
    )
    harness.wait_for_output_count("alpha", 3)

    harness.assert_showing_workflow("alpha", color=(40, 120, 200))


def test_pending_final_does_not_override_manual_reselection(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """A pending generated projection should not beat immediate user selection."""

    harness.add_workflow("alpha", activate=True)
    run = harness.start_run("alpha", run_index=1)
    harness.emit_output(
        run,
        OutputSpec("alpha-save", "Alpha", (45, 125, 205), batch_index=0),
    )
    harness.wait_for_output_count("alpha", 1)
    harness.emit_output(
        run,
        OutputSpec("alpha-save", "Alpha", (125, 205, 45), batch_index=1),
    )
    harness.wait_for_output_count("alpha", 2)
    first_output_id = harness.output_ids("alpha")[0]

    harness.emit_output(
        run,
        OutputSpec("alpha-save", "Alpha", (205, 125, 45), batch_index=2),
    )
    harness.select_output_id(first_output_id)
    workflow_id = harness.workflows["alpha"].workflow_id
    selected = harness.fingerprint()
    assert selected.workflow_output_focus_modes[workflow_id] == "manual", selected
    assert selected.workflow_output_routes[workflow_id][4] == first_output_id, selected
    harness.wait_for_output_count("alpha", 3)

    settled = harness.fingerprint()
    assert settled.workflow_output_focus_modes[workflow_id] == "manual", settled
    assert settled.workflow_output_routes[workflow_id][4] == first_output_id, settled
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
    assert state.active_image_id is None, state
    assert state.active_composition_id is None, state
    assert state.active_image_is_null, state


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

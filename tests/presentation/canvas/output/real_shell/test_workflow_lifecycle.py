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

"""Verify Output work is pruned across close, clear, failure, and rename lifecycles."""

from __future__ import annotations

from tests.presentation.canvas.output.real_shell.synchronization import (
    wait_for_output_delivery,
    wait_for_output_failure,
)
from tests.support.real_output_canvas.harness import RealShellOutputCanvasHarness
from tests.support.real_output_canvas.models import OutputSpec


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
    wait_for_output_delivery(harness)

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
    wait_for_output_delivery(harness)

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
    wait_for_output_delivery(harness)

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
    wait_for_output_failure(harness, report_count=1)

    assert harness.output_count("alpha") == 1
    assert len(harness.shell.error_reports) == 1
    harness.assert_showing_workflow("alpha", color=(80, 160, 220))


def test_successful_new_result_replaces_previous_only_after_preparation(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Keep the old result through failure, then atomically replace it on success."""

    harness.add_workflow("alpha", activate=True)
    baseline_run = harness.start_run("alpha", run_index=1)
    harness.emit_output(
        baseline_run,
        OutputSpec("alpha-save", "Alpha", (75, 155, 215)),
    )
    harness.wait_for_output_count("alpha", 1)
    baseline_id = harness.output_ids("alpha")[0]
    replacement_run = harness.start_run("alpha", run_index=2)

    harness.emit_unloadable_output(
        replacement_run,
        OutputSpec("alpha-save", "Alpha", (215, 75, 155)),
    )
    wait_for_output_failure(harness, report_count=1)
    assert harness.output_ids("alpha") == (baseline_id,)
    harness.assert_showing_workflow("alpha", color=(75, 155, 215))

    harness.emit_output(
        replacement_run,
        OutputSpec("alpha-save", "Alpha", (215, 155, 75)),
    )
    harness.wait_until(
        lambda: (
            len(harness.output_ids("alpha")) == 1
            and harness.output_ids("alpha")[0] != baseline_id
        )
    )

    harness.assert_showing_workflow("alpha", color=(215, 155, 75))


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
    wait_for_output_delivery(harness)

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
    wait_for_output_delivery(harness)

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
    baseline_id = harness.output_ids("alpha")[0]
    harness.show_canvas("Input")
    generated_run = harness.start_run("alpha", run_index=2)
    harness.emit_output(
        generated_run,
        OutputSpec("alpha-save", "Alpha", (210, 90, 70)),
    )
    harness.wait_until(
        lambda: (
            len(harness.output_ids("alpha")) == 1
            and harness.output_ids("alpha")[0] != baseline_id
        )
    )
    hidden_state = harness.fingerprint()
    assert "workflow-alpha" in hidden_state.pending_projection_workflows, hidden_state

    harness.clear_output_for("alpha")
    wait_for_output_delivery(harness)

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
    wait_for_output_delivery(harness)

    state = harness.fingerprint()
    assert "workflow-alpha" not in state.workflow_output_image_ids, state
    assert "workflow-alpha" not in state.pending_projection_workflows, state
    harness.assert_showing_workflow("renamed-alpha", color=(75, 155, 215))

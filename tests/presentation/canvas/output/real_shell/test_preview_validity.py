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

"""Verify final and preview validity across run ordering and source lanes."""

from __future__ import annotations

from tests.presentation.canvas.output.real_shell.synchronization import (
    wait_for_output_delivery,
)
from tests.support.real_output_canvas.harness import RealShellOutputCanvasHarness
from tests.support.real_output_canvas.models import OutputSpec


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
    wait_for_output_delivery(harness)

    assert harness.output_count("alpha") == 0
    state = harness.fingerprint()
    assert state.active_image_id is None
    assert state.active_composition_id is None


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
    baseline_id = harness.output_ids("alpha")[0]
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
    harness.wait_until(
        lambda: (
            len(harness.output_ids("alpha")) == 1
            and harness.output_ids("alpha")[0] != baseline_id
        )
    )
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
    wait_for_output_delivery(harness)

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
    wait_for_output_delivery(harness)

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
    wait_for_output_delivery(harness)

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
    baseline_id = harness.output_ids("alpha")[0]
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
    harness.wait_until(
        lambda: (
            len(harness.output_ids("alpha")) == 1
            and harness.output_ids("alpha")[0] != baseline_id
        )
    )

    harness.wait_for_preview_count(1)
    harness.assert_showing_workflow("alpha", color=(210, 60, 130))

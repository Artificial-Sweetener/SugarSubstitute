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

"""Verify separator abuse behavior through the production-mounted editor."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.prompt_editor_abuse.models import PromptAbuseAction, PromptAbuseScenario
from tools.prompt_editor_abuse.prompt_workloads import prompt_scenarios
from tools.prompt_editor_abuse.real_shell_driver import run_real_shell_scenario
from tools.prompt_editor_abuse.structural_instrumentation import (
    prompt_abuse_structural_instrumentation,
)


@pytest.mark.parametrize(
    "scenario_name",
    (
        "region-separator-horizontal-atomic-navigation",
        "region-separator-vertical-navigation",
        "region-separator-mouse-placement",
        "region-separator-raw-rich-boundary",
        "region-separator-topology-promotion",
        "region-separator-adjacent-authoring",
        "region-separator-adjacent-partition-population",
        "region-separator-continued-authoring",
        "region-separator-nearby-authoring",
        "region-separator-delete-join-split",
        "region-separator-paste-selection-resize",
        "region-separator-multi-line-break",
        "region-separator-canvas-lifecycle",
    ),
)
def test_real_shell_region_separator_abuse_scenarios_remain_exact(
    tmp_path: Path,
    scenario_name: str,
) -> None:
    """Retain exact source, caret, projection, and chrome owners."""

    scenario = next(
        candidate for candidate in prompt_scenarios() if candidate.name == scenario_name
    )

    with prompt_abuse_structural_instrumentation(enabled=True):
        result = run_real_shell_scenario(
            scenario,
            repetition=0,
            artifact_root=tmp_path,
        )

    assert result.correct, (
        result.invariant_violations,
        tuple(
            (
                sample.label,
                sample.actual_source_on_mismatch,
                sample.actual_cursor_position,
                sample.expected_cursor_position,
                sample.feature_mismatch,
                sample.layout_fragment_ownership_mismatch,
            )
            for sample in result.dispatch_samples
            if not (
                sample.source_exact
                and sample.caret_exact
                and sample.selection_exact
                and sample.feature_exact
                and sample.layout_fragment_ownership_valid is not False
            )
        ),
    )
    if scenario_name == "region-separator-adjacent-partition-population":
        rebuild_actions = {
            delta.action_index
            for delta in result.action_owner_deltas
            if dict(delta.counter_deltas).get(
                "instrumented_projection_rebuild_count",
                0.0,
            )
            != 0.0
        }
        assert rebuild_actions == {0}
    if scenario_name == "region-separator-canvas-lifecycle":
        canvas_delta = next(
            delta
            for delta in result.action_owner_deltas
            if delta.label == "canvas_round_trip"
        )
        canvas_counters = dict(canvas_delta.counter_deltas)
        assert canvas_counters.get("region_chrome_prepare_count", 0.0) == 0.0
        assert canvas_counters.get("instrumented_projection_rebuild_count", 0.0) == 0.0
        assert canvas_counters.get("instrumented_layout_snapshot_count", 0.0) == 0.0


@pytest.mark.parametrize(
    "scenario_name",
    (
        "regional-separator-cross-partition-drag",
        "regional-separator-leading-partition-exit",
        "regional-separator-trailing-partition-exit",
        "regional-separator-multi-partition-drag",
    ),
)
def test_real_shell_regional_reorder_keeps_destinations_and_landing_shadow(
    tmp_path: Path,
    scenario_name: str,
) -> None:
    """Retain every cross-region target and prepared landing shadow."""

    scenario = next(
        candidate for candidate in prompt_scenarios() if candidate.name == scenario_name
    )

    with prompt_abuse_structural_instrumentation(enabled=True):
        result = run_real_shell_scenario(
            scenario,
            repetition=0,
            artifact_root=tmp_path,
        )

    assert result.correct, (
        result.invariant_violations,
        tuple(
            (sample.label, sample.feature_mismatch, sample.actual_source_on_mismatch)
            for sample in result.dispatch_samples
            if not sample.feature_exact or not sample.source_exact
        ),
    )


@pytest.mark.parametrize("seed", (7, 19, 73))
def test_real_shell_seeded_region_separator_abuse_remains_exact(
    tmp_path: Path,
    seed: int,
) -> None:
    """Vary mixed separator abuse while retaining every owner invariant."""

    scenario = next(
        candidate
        for candidate in prompt_scenarios(seed=seed)
        if candidate.name == "region-separator-seeded-churn"
    )

    with prompt_abuse_structural_instrumentation(enabled=True):
        result = run_real_shell_scenario(
            scenario,
            repetition=0,
            artifact_root=tmp_path,
        )

    assert result.correct, (
        result.invariant_violations,
        result.structural_violations,
        tuple(
            (
                sample.label,
                sample.actual_source_on_mismatch,
                sample.actual_cursor_position,
                sample.expected_cursor_position,
                sample.feature_mismatch,
                sample.layout_fragment_ownership_mismatch,
            )
            for sample in result.dispatch_samples
            if not (
                sample.source_exact
                and sample.caret_exact
                and sample.selection_exact
                and sample.feature_exact
                and sample.layout_fragment_ownership_valid is not False
            )
        ),
    )


def test_real_shell_abuse_driver_keeps_every_wrapping_keystroke_visible(
    tmp_path: Path,
) -> None:
    """Keep a visual owner for every source and caret wrap transition."""

    typed_text = "sfhjaklfhj jasfklaj flaosjufioewjflafiws"
    result = run_real_shell_scenario(
        PromptAbuseScenario(
            "wrapping-visual-owner",
            "",
            (
                PromptAbuseAction(
                    "type",
                    value=typed_text,
                    expected_source=typed_text,
                    expected_cursor_position=len(typed_text),
                ),
            ),
            typed_text,
            cursor_position=0,
            viewport_size=(120, 240),
        ),
        repetition=0,
        artifact_root=tmp_path,
    )

    assert result.correct
    assert all(
        sample.visible_source_current_after_dispatch is True
        for sample in result.dispatch_samples
    )
    assert all(
        sample.visible_caret_current_after_dispatch is True
        for sample in result.dispatch_samples
    )

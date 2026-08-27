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

"""Verify real-shell prompt-abuse driver instrumentation."""

from __future__ import annotations

from pathlib import Path

from tools.prompt_editor_abuse.models import PromptAbuseAction, PromptAbuseScenario
from tools.prompt_editor_abuse.prompt_workloads import prompt_scenarios
from tools.prompt_editor_abuse.real_shell_driver import run_real_shell_scenario
from tools.prompt_editor_abuse.replay import scenario_prefix


def test_real_shell_abuse_driver_measures_exact_untraced_input(tmp_path: Path) -> None:
    """The low-overhead driver should measure the production-mounted key route."""

    result = run_real_shell_scenario(
        PromptAbuseScenario(
            "driver-smoke",
            "alpha, ",
            (
                PromptAbuseAction(
                    "type",
                    value="xyz",
                    expected_source="alpha, xyz",
                    expected_cursor_position=len("alpha, xyz"),
                ),
            ),
            "alpha, xyz",
            cursor_position=len("alpha, "),
        ),
        repetition=0,
        artifact_root=tmp_path,
    )

    assert result.correct
    assert len(result.dispatch_samples) == 3
    assert all(sample.source_exact for sample in result.dispatch_samples)
    assert all(
        sample.visible_source_current_after_dispatch is True
        for sample in result.dispatch_samples
    )
    assert all(
        sample.visible_caret_current_after_dispatch is True
        for sample in result.dispatch_samples
    )
    assert result.latency.maximum_ms > 0.0
    assert result.deep_trace_enabled is False


def test_real_shell_abuse_driver_measures_each_lifecycle_transition(
    tmp_path: Path,
) -> None:
    """Round-trip torture should budget each visible switch as one operation."""

    result = run_real_shell_scenario(
        PromptAbuseScenario(
            "lifecycle-step-timing",
            "alpha",
            (
                PromptAbuseAction(
                    "workflow_round_trip",
                    expected_source="alpha",
                    expected_cursor_position=0,
                ),
                PromptAbuseAction(
                    "canvas_round_trip",
                    expected_source="alpha",
                    expected_cursor_position=0,
                ),
            ),
            "alpha",
        ),
        repetition=0,
        artifact_root=tmp_path,
    )

    assert result.correct
    assert [sample.label for sample in result.dispatch_samples] == [
        "workflow:switch-away",
        "workflow:return",
        "canvas:switch-away",
        "canvas:return",
    ]
    assert all(sample.dispatch_ms > 0.0 for sample in result.dispatch_samples)


def test_real_shell_abuse_driver_checks_projection_ownership_after_each_action(
    tmp_path: Path,
) -> None:
    """A single mode switch should immediately retain canonical owner agreement."""

    source = "(cat:1.05), suffix"
    result = run_real_shell_scenario(
        PromptAbuseScenario(
            "single-raw-mode-owner-check",
            source,
            (
                PromptAbuseAction(
                    "display_mode",
                    value="raw",
                    expected_source=source,
                    expected_cursor_position=len(source),
                ),
            ),
            source,
            cursor_position=len(source),
        ),
        repetition=0,
        artifact_root=tmp_path,
    )

    assert result.correct
    assert len(result.dispatch_samples) == 1
    sample = result.dispatch_samples[0]
    assert sample.active_projection_ownership_valid is True
    assert sample.layout_projection_ownership_valid is True


def test_real_shell_abuse_driver_rebinds_fragments_after_autocomplete_churn(
    tmp_path: Path,
) -> None:
    """Queued autocomplete typing must keep layout fragments on current runs."""

    scenario = scenario_prefix(
        next(
            candidate
            for candidate in prompt_scenarios()
            if candidate.name == "autocomplete-race-churn"
        ),
        action_count=6,
    )
    result = run_real_shell_scenario(
        scenario,
        repetition=0,
        artifact_root=tmp_path,
    )

    assert result.correct
    assert all(
        sample.layout_fragment_ownership_valid is not False
        for sample in result.dispatch_samples
    )


def test_seeded_abuse_selection_replace_keeps_fragment_owners(
    tmp_path: Path,
) -> None:
    """Selection replacement must retain current fragment ownership."""

    scenario = scenario_prefix(
        next(
            candidate
            for candidate in prompt_scenarios(seed=7)
            if candidate.name == "seeded-mixed-abuse"
        ),
        action_count=17,
    )
    result = run_real_shell_scenario(
        scenario,
        repetition=0,
        artifact_root=tmp_path,
    )

    assert result.correct
    assert all(
        sample.layout_fragment_ownership_valid is not False
        for sample in result.dispatch_samples
    )

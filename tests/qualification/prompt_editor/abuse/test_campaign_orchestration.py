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

"""Test prompt-editor abuse campaign-orchestration contracts."""

from __future__ import annotations

import json
from pathlib import Path


from tools.prompt_editor_abuse.campaign import run_campaign
from tools.prompt_editor_abuse.comparison import (
    compare_report_files,
    format_comparison,
)
from tools.prompt_editor_abuse.models import (
    PromptAbuseAction,
    PromptAbuseDispatchSample,
    PromptAbuseScenario,
    PromptAbuseScenarioResult,
)
from tools.prompt_editor_abuse.reporting import format_summary, write_report
from tools.prompt_editor_abuse.replay import load_report_scenarios, scenario_prefix
from tools.prompt_editor_abuse.statistics import summarize_latencies


def test_campaign_repeats_scenarios_and_writes_assistant_readable_report(
    tmp_path: Path,
) -> None:
    """Campaign orchestration should retain raw samples and reproducible inputs."""

    scenario = PromptAbuseScenario(
        "fake",
        "alpha",
        (
            PromptAbuseAction(
                "type",
                value=" xy",
                expected_source="alpha xy",
                expected_cursor_position=8,
            ),
        ),
        "alpha xy",
        cursor_position=5,
    )
    calls: list[tuple[str, int, bool]] = []

    def fake_runner(
        run_scenario: PromptAbuseScenario,
        *,
        repetition: int,
        artifact_root: Path,
        deep_trace: bool,
    ) -> PromptAbuseScenarioResult:
        """Return deterministic evidence while recording orchestration inputs."""

        assert artifact_root == tmp_path
        calls.append((run_scenario.name, repetition, deep_trace))
        samples = (
            PromptAbuseDispatchSample(0, 0, "type:' '", 2.0 + repetition, True, True),
            PromptAbuseDispatchSample(0, 1, "type:'x'", 4.0 + repetition, True, True),
            PromptAbuseDispatchSample(0, 2, "type:'y'", 8.0 + repetition, True, True),
        )
        return PromptAbuseScenarioResult(
            scenario=run_scenario,
            repetition=repetition,
            dispatch_samples=samples,
            latency=summarize_latencies(
                tuple(sample.dispatch_ms for sample in samples)
            ),
            burst_dispatch_ms=14.0,
            settle_ms=1.0,
            actual_text_on_mismatch=None,
            projection_current=True,
            semantic_current=True,
            invariant_violations=(),
            deep_trace_enabled=deep_trace,
        )

    report = run_campaign(
        (scenario,),
        repetitions=2,
        seed=41,
        frame_budget_ms=16.667,
        artifact_root=tmp_path,
        deep_trace=False,
        scenario_runner=fake_runner,
        platform_name=lambda: "offscreen-test",
    )
    report_path = tmp_path / "report.json"
    write_report(report, report_path)
    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert calls == [("fake", 0, False), ("fake", 1, False)]
    assert report.correctness_passed
    assert report.structural_performance_passed
    assert report.timing_target_passed
    assert payload["seed"] == 41
    assert payload["results"][0]["scenario"]["actions"][0]["value"] == " xy"
    assert "p95=" in format_summary(report)

    loaded = load_report_scenarios(report_path, scenario_name="fake")
    assert loaded == (scenario,)
    prefix = scenario_prefix(loaded[0], action_count=1)
    assert prefix.expected_text == "alpha xy"
    assert prefix.name == "fake-actions-1"

    comparison = compare_report_files(report_path, report_path)
    assert not comparison.correctness_regressed
    assert comparison.scenarios[0].p95.delta_ms == 0.0
    assert "fake" in format_comparison(comparison)

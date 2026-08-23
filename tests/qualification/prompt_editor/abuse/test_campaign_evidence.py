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

"""Test prompt-editor abuse campaign-evidence contracts."""

from __future__ import annotations

from pathlib import Path


from tools.prompt_editor_abuse.action_counter_probe import (
    PromptAbuseActionCounterProbe,
)
from tools.prompt_editor_abuse.campaign import run_campaign
from tools.prompt_editor_abuse.models import (
    PromptAbuseAction,
    PromptAbuseCampaignReport,
    PromptAbuseScenario,
    PromptAbuseScenarioResult,
)
from tools.prompt_editor_abuse.reporting import format_summary
from tools.prompt_editor_abuse.statistics import summarize_latencies
from tools.prompt_editor_abuse.structural_instrumentation import (
    prompt_abuse_structural_instrumentation,
)


def test_campaign_reports_structural_and_timing_evidence_independently() -> None:
    """Fast clocks must not conceal structurally unbounded editor work."""

    scenario = PromptAbuseScenario(
        "structurally-heavy",
        "alpha",
        (PromptAbuseAction("key", value="right", expected_source="alpha"),),
        "alpha",
    )
    fast = summarize_latencies((1.0,))
    result = PromptAbuseScenarioResult(
        scenario=scenario,
        repetition=0,
        dispatch_samples=(),
        latency=fast,
        burst_dispatch_ms=1.0,
        settle_ms=0.0,
        actual_text_on_mismatch=None,
        projection_current=True,
        semantic_current=True,
        invariant_violations=(),
        deep_trace_enabled=False,
        structural_violations=("structural_budget:test",),
    )
    report = PromptAbuseCampaignReport(
        revision="test",
        qt_platform="offscreen",
        seed=7,
        frame_budget_ms=16.667,
        results=(result,),
    )

    assert not report.structural_performance_passed
    assert report.timing_target_passed
    assert "structural_violations=('structural_budget:test',)" in format_summary(report)


def test_structural_instrumentation_attributes_external_counts_per_action() -> None:
    """Opt-in method instrumentation should remain attributable by action."""

    probe = PromptAbuseActionCounterProbe(object())
    with prompt_abuse_structural_instrumentation(enabled=True) as instrumentation:
        assert instrumentation is not None
        probe.begin_unit()
        instrumentation.projection_rebuild.record(2.0)
        instrumentation.layout_snapshot.record(3.0)
        delta = probe.finish_unit(action_index=4, unit_index=0, label="type:'x'")

    assert dict(delta.counter_deltas) == {
        "instrumented_layout_snapshot_count": 1.0,
        "instrumented_projection_rebuild_count": 1.0,
    }


def test_structural_campaign_marks_clock_evidence_as_instrumented(
    tmp_path: Path,
) -> None:
    """Structural runs must never masquerade as reference timing evidence."""

    scenario = PromptAbuseScenario(
        "fake",
        "alpha",
        (PromptAbuseAction("key", value="right", expected_source="alpha"),),
        "alpha",
    )

    def fake_runner(
        run_scenario: PromptAbuseScenario,
        *,
        repetition: int,
        artifact_root: Path,
        deep_trace: bool,
    ) -> PromptAbuseScenarioResult:
        """Return a correct empty result inside the instrumented campaign."""

        _ = (repetition, artifact_root, deep_trace)
        return PromptAbuseScenarioResult(
            scenario=run_scenario,
            repetition=0,
            dispatch_samples=(),
            latency=summarize_latencies(()),
            burst_dispatch_ms=0.0,
            settle_ms=0.0,
            actual_text_on_mismatch=None,
            projection_current=True,
            semantic_current=True,
            invariant_violations=(),
            deep_trace_enabled=False,
        )

    report = run_campaign(
        (scenario,),
        repetitions=1,
        seed=7,
        frame_budget_ms=16.667,
        artifact_root=tmp_path,
        structural_probe=True,
        scenario_runner=fake_runner,
        platform_name=lambda: "offscreen-test",
    )

    assert report.structural_probe_enabled
    assert not report.timing_evidence_representative
    assert "timing_confidence=instrumented" in format_summary(report)

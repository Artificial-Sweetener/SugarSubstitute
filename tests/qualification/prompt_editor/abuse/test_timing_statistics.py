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

"""Test prompt-editor abuse timing-statistics and timing-reporting contracts."""

from __future__ import annotations


from tools.prompt_editor_abuse.models import (
    PromptAbuseAction,
    PromptAbuseDispatchSample,
    PromptAbuseCampaignReport,
    PromptAbuseLatencyBreakdown,
    PromptAbuseLatencySummary,
    PromptAbuseScenario,
    PromptAbuseScenarioResult,
    PromptAbuseSystemLoad,
)
from tools.prompt_editor_abuse.reporting import format_summary
from tools.prompt_editor_abuse.statistics import percentile, summarize_latencies


def test_latency_summary_uses_nearest_rank_percentiles() -> None:
    """Latency summaries should preserve tail spikes for assistant ranking."""

    values = tuple(float(index) for index in range(1, 101))

    summary = summarize_latencies(values)

    assert summary == PromptAbuseLatencySummary(
        p50_ms=50.0,
        p95_ms=95.0,
        p99_ms=99.0,
        maximum_ms=100.0,
    )
    assert percentile((), 95) == 0.0


def test_timing_target_rejects_slow_non_typing_operations() -> None:
    """The reference target must include interaction and queued-work stalls."""

    scenario = PromptAbuseScenario(
        "interaction-only",
        "alpha",
        (PromptAbuseAction("key_press", value="alt", expected_source="alpha"),),
        "alpha",
    )
    zero = summarize_latencies(())
    slow = summarize_latencies((28.0, 35.0, 42.0))
    result = PromptAbuseScenarioResult(
        scenario=scenario,
        repetition=0,
        dispatch_samples=(
            PromptAbuseDispatchSample(
                0,
                0,
                "key_press:'alt'",
                35.0,
                True,
                True,
                latency_class="interaction",
            ),
        ),
        latency=slow,
        burst_dispatch_ms=35.0,
        settle_ms=0.0,
        actual_text_on_mismatch=None,
        projection_current=True,
        semantic_current=True,
        invariant_violations=(),
        deep_trace_enabled=False,
        latency_breakdown=PromptAbuseLatencyBreakdown(
            text_input=zero,
            interaction=slow,
            lifecycle=zero,
            backlog_drain=zero,
            text_input_count=0,
            interaction_count=3,
            lifecycle_count=0,
            backlog_drain_count=0,
        ),
    )

    report = PromptAbuseCampaignReport(
        revision="test",
        qt_platform="offscreen",
        seed=7,
        frame_budget_ms=16.667,
        results=(result,),
    )

    assert not report.timing_target_passed


def test_timing_target_rejects_tail_spikes_hidden_by_p95() -> None:
    """A nominal p95 must not hide visible p99 or maximum frame stalls."""

    scenario = PromptAbuseScenario(
        "tail-spike",
        "alpha",
        (PromptAbuseAction("key", value="right", expected_source="alpha"),),
        "alpha",
    )
    timings = tuple(4.0 for _index in range(99)) + (80.0,)
    latency = summarize_latencies(timings)
    zero = summarize_latencies(())
    result = PromptAbuseScenarioResult(
        scenario=scenario,
        repetition=0,
        dispatch_samples=(),
        latency=latency,
        burst_dispatch_ms=sum(timings),
        settle_ms=0.0,
        actual_text_on_mismatch=None,
        projection_current=True,
        semantic_current=True,
        invariant_violations=(),
        deep_trace_enabled=False,
        latency_breakdown=PromptAbuseLatencyBreakdown(
            text_input=latency,
            interaction=zero,
            lifecycle=zero,
            backlog_drain=zero,
            text_input_count=len(timings),
            interaction_count=0,
            lifecycle_count=0,
            backlog_drain_count=0,
        ),
    )
    report = PromptAbuseCampaignReport(
        revision="test",
        qt_platform="offscreen",
        seed=7,
        frame_budget_ms=16.667,
        results=(result,),
    )

    assert latency.p95_ms == 4.0
    assert not report.timing_target_passed


def test_campaign_report_marks_externally_contended_timing_environment() -> None:
    """Assistant summaries should distinguish editor cost from competing CPU work."""

    report = PromptAbuseCampaignReport(
        revision="test",
        qt_platform="offscreen",
        seed=7,
        frame_budget_ms=16.667,
        results=(),
        system_load=PromptAbuseSystemLoad(
            elapsed_seconds=5.0,
            logical_cpu_count=32,
            system_cpu_percent=62.0,
            harness_cpu_percent=3.0,
            competing_cpu_percent=59.0,
        ),
    )

    summary = format_summary(report)

    assert report.system_load is not None
    assert report.system_load.contended
    assert not report.timing_evidence_representative
    assert "competing=59.0%" in summary
    assert "timing_confidence=contended" in summary


def test_campaign_report_does_not_claim_unmeasured_timing_is_representative() -> None:
    """Missing load evidence must remain explicit in assistant summaries."""

    report = PromptAbuseCampaignReport(
        revision="test",
        qt_platform="offscreen",
        seed=7,
        frame_budget_ms=16.667,
        results=(),
    )

    assert not report.timing_evidence_representative
    assert "timing_confidence=unmeasured" in format_summary(report)

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

"""Measure hostile actions against one already-mounted production editor."""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter

from PySide6.QtWidgets import QWidget

from .action_counter_probe import PromptAbuseActionCounterProbe
from .action_driver import PromptAbuseActionHost, dispatch_action
from .models import (
    PromptAbuseAction,
    PromptAbuseActionOwnerDelta,
    PromptAbuseCorrectnessSnapshot,
    PromptAbuseDispatchSample,
    PromptAbuseLatencyBreakdown,
    PromptAbuseScenario,
    PromptAbuseScenarioResult,
)
from .statistics import summarize_latencies
from .structural_policy import prompt_abuse_structural_violations

type PromptAbuseSettler = Callable[[str], tuple[float, bool]]
type PromptAbuseCorrectnessCapture = Callable[[], PromptAbuseCorrectnessSnapshot]
type PromptAbuseActionObserver = Callable[[int, PromptAbuseAction], None]


def execute_mounted_scenario(
    scenario: PromptAbuseScenario,
    *,
    repetition: int,
    editor: object,
    target: QWidget,
    settle: PromptAbuseSettler,
    capture_correctness: PromptAbuseCorrectnessCapture,
    deep_trace_enabled: bool,
    after_action: PromptAbuseActionObserver | None = None,
    action_host: PromptAbuseActionHost | None = None,
) -> PromptAbuseScenarioResult:
    """Dispatch a scenario and return timing plus authoritative correctness."""

    action_host = action_host or PromptAbuseActionHost()
    dispatch_samples: list[PromptAbuseDispatchSample] = []
    counter_probe = PromptAbuseActionCounterProbe(editor)
    action_owner_deltas: list[PromptAbuseActionOwnerDelta] = []
    burst_started_at = perf_counter()
    for action_index, action in enumerate(scenario.actions):
        dispatch_samples.extend(
            dispatch_action(
                action_host,
                editor,
                target,
                action,
                action_index=action_index,
                runtime_telemetry=deep_trace_enabled,
                counter_probe=counter_probe,
                counter_deltas=action_owner_deltas,
            )
        )
        if after_action is not None:
            after_action(action_index, action)
    burst_dispatch_ms = (perf_counter() - burst_started_at) * 1_000.0
    settle_ms, settled = settle(scenario.expected_text)
    correctness = capture_correctness()
    violations = list(correctness.invariant_violations)
    if not settled:
        violations.append("editor_did_not_settle_before_timeout")
    if correctness.actual_text != scenario.expected_text:
        violations.append("final_source_mismatch")
    timings_by_class = {
        latency_class: tuple(
            sample.dispatch_ms
            for sample in dispatch_samples
            if sample.latency_class == latency_class
        )
        for latency_class in (
            "text_input",
            "interaction",
            "lifecycle",
            "backlog_drain",
        )
    }
    text_input_timings = timings_by_class["text_input"]
    governed_timings = tuple(sample.dispatch_ms for sample in dispatch_samples)
    action_owner_delta_snapshot = tuple(action_owner_deltas)
    return PromptAbuseScenarioResult(
        scenario=scenario,
        repetition=repetition,
        dispatch_samples=tuple(dispatch_samples),
        latency=summarize_latencies(governed_timings),
        burst_dispatch_ms=burst_dispatch_ms,
        settle_ms=settle_ms,
        actual_text_on_mismatch=(
            None
            if correctness.actual_text == scenario.expected_text
            else correctness.actual_text
        ),
        projection_current=correctness.projection_current,
        semantic_current=correctness.semantic_current,
        invariant_violations=tuple(dict.fromkeys(violations)),
        deep_trace_enabled=deep_trace_enabled,
        latency_breakdown=PromptAbuseLatencyBreakdown(
            text_input=summarize_latencies(text_input_timings),
            interaction=summarize_latencies(timings_by_class["interaction"]),
            lifecycle=summarize_latencies(timings_by_class["lifecycle"]),
            backlog_drain=summarize_latencies(timings_by_class["backlog_drain"]),
            text_input_count=len(text_input_timings),
            interaction_count=len(timings_by_class["interaction"]),
            lifecycle_count=len(timings_by_class["lifecycle"]),
            backlog_drain_count=len(timings_by_class["backlog_drain"]),
        ),
        action_owner_deltas=action_owner_delta_snapshot,
        structural_violations=prompt_abuse_structural_violations(
            action_owner_delta_snapshot
        ),
    )


__all__ = [
    "PromptAbuseCorrectnessCapture",
    "PromptAbuseActionObserver",
    "PromptAbuseSettler",
    "execute_mounted_scenario",
]

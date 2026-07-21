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

"""Compare prompt-editor campaign distributions across two saved reports."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from statistics import median
from typing import Any, cast


@dataclass(frozen=True, slots=True)
class PromptAbuseMetricDelta:
    """Describe one baseline and candidate timing metric."""

    baseline_ms: float
    candidate_ms: float
    delta_ms: float
    delta_percent: float | None


@dataclass(frozen=True, slots=True)
class PromptAbuseScenarioComparison:
    """Compare aggregate correctness and latency for one named scenario."""

    scenario_name: str
    baseline_correct: bool
    candidate_correct: bool
    baseline_repetitions: int
    candidate_repetitions: int
    p50: PromptAbuseMetricDelta
    p95: PromptAbuseMetricDelta
    p99: PromptAbuseMetricDelta
    maximum: PromptAbuseMetricDelta
    settle: PromptAbuseMetricDelta


@dataclass(frozen=True, slots=True)
class PromptAbuseComparisonReport:
    """Record comparable revisions and per-scenario performance changes."""

    baseline_revision: str
    candidate_revision: str
    scenarios: tuple[PromptAbuseScenarioComparison, ...]

    @property
    def correctness_regressed(self) -> bool:
        """Return whether a previously correct scenario became incorrect."""

        return any(
            scenario.baseline_correct and not scenario.candidate_correct
            for scenario in self.scenarios
        )


def compare_report_files(
    baseline_path: Path,
    candidate_path: Path,
) -> PromptAbuseComparisonReport:
    """Return a scenario-aligned comparison of two JSON campaign reports."""

    baseline = _load_report(baseline_path)
    candidate = _load_report(candidate_path)
    baseline_results = _results_by_scenario(baseline)
    candidate_results = _results_by_scenario(candidate)
    shared_names = sorted(baseline_results.keys() & candidate_results.keys())
    if not shared_names:
        raise ValueError("Prompt abuse reports contain no shared scenarios.")
    return PromptAbuseComparisonReport(
        baseline_revision=str(baseline.get("revision", "unknown")),
        candidate_revision=str(candidate.get("revision", "unknown")),
        scenarios=tuple(
            _compare_scenario(
                scenario_name,
                baseline_results[scenario_name],
                candidate_results[scenario_name],
            )
            for scenario_name in shared_names
        ),
    )


def write_comparison(report: PromptAbuseComparisonReport, path: Path) -> None:
    """Write one stable assistant-readable comparison artifact."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(report), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def format_comparison(report: PromptAbuseComparisonReport) -> str:
    """Return a compact largest-p95-regression-first comparison."""

    rows = [
        f"baseline={report.baseline_revision} candidate={report.candidate_revision} "
        f"correctness_regressed={report.correctness_regressed}"
    ]
    for scenario in sorted(
        report.scenarios,
        key=lambda item: item.p95.delta_ms,
        reverse=True,
    ):
        rows.append(
            f"{scenario.scenario_name} correct="
            f"{scenario.baseline_correct}->{scenario.candidate_correct} "
            f"p50={_format_delta(scenario.p50)} "
            f"p95={_format_delta(scenario.p95)} "
            f"max={_format_delta(scenario.maximum)} "
            f"settle={_format_delta(scenario.settle)}"
        )
    return "\n".join(rows)


def _load_report(path: Path) -> dict[str, Any]:
    """Load one JSON campaign report at the serialization boundary."""

    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _results_by_scenario(
    report: dict[str, Any],
) -> dict[str, tuple[dict[str, Any], ...]]:
    """Group serialized repetitions by stable scenario name."""

    grouped: dict[str, list[dict[str, Any]]] = {}
    for result in cast(list[dict[str, Any]], report.get("results", [])):
        scenario = cast(dict[str, Any], result["scenario"])
        grouped.setdefault(str(scenario["name"]), []).append(result)
    return {name: tuple(results) for name, results in grouped.items()}


def _compare_scenario(
    scenario_name: str,
    baseline_results: tuple[dict[str, Any], ...],
    candidate_results: tuple[dict[str, Any], ...],
) -> PromptAbuseScenarioComparison:
    """Compare aggregate metrics for one aligned scenario."""

    return PromptAbuseScenarioComparison(
        scenario_name=scenario_name,
        baseline_correct=all(_result_correct(result) for result in baseline_results),
        candidate_correct=all(_result_correct(result) for result in candidate_results),
        baseline_repetitions=len(baseline_results),
        candidate_repetitions=len(candidate_results),
        p50=_metric_delta(baseline_results, candidate_results, "p50_ms"),
        p95=_metric_delta(baseline_results, candidate_results, "p95_ms"),
        p99=_metric_delta(baseline_results, candidate_results, "p99_ms"),
        maximum=_metric_delta(baseline_results, candidate_results, "maximum_ms"),
        settle=_top_level_metric_delta(
            baseline_results,
            candidate_results,
            "settle_ms",
        ),
    )


def _result_correct(result: dict[str, Any]) -> bool:
    """Return serialized correctness using the same observable result fields."""

    samples = cast(list[dict[str, Any]], result.get("dispatch_samples", []))
    return bool(
        result.get("actual_text_on_mismatch") is None
        and result.get("projection_current", False)
        and result.get("semantic_current", False)
        and not result.get("invariant_violations", [])
        and all(
            sample.get("source_exact", False)
            and sample.get("caret_exact", False)
            and sample.get("visible_source_current_after_dispatch") is not False
            and sample.get("visible_caret_current_after_dispatch") is not False
            for sample in samples
        )
    )


def _metric_delta(
    baseline_results: tuple[dict[str, Any], ...],
    candidate_results: tuple[dict[str, Any], ...],
    metric_name: str,
) -> PromptAbuseMetricDelta:
    """Compare medians of one serialized latency-summary metric."""

    return _delta(
        median(
            float(cast(dict[str, Any], result["latency"])[metric_name])
            for result in baseline_results
        ),
        median(
            float(cast(dict[str, Any], result["latency"])[metric_name])
            for result in candidate_results
        ),
    )


def _top_level_metric_delta(
    baseline_results: tuple[dict[str, Any], ...],
    candidate_results: tuple[dict[str, Any], ...],
    metric_name: str,
) -> PromptAbuseMetricDelta:
    """Compare medians of one top-level scenario result metric."""

    return _delta(
        median(float(result[metric_name]) for result in baseline_results),
        median(float(result[metric_name]) for result in candidate_results),
    )


def _delta(baseline: float, candidate: float) -> PromptAbuseMetricDelta:
    """Return absolute and percentage change for one metric pair."""

    delta = candidate - baseline
    return PromptAbuseMetricDelta(
        baseline_ms=baseline,
        candidate_ms=candidate,
        delta_ms=delta,
        delta_percent=None if baseline == 0.0 else (delta / baseline) * 100.0,
    )


def _format_delta(delta: PromptAbuseMetricDelta) -> str:
    """Return one compact baseline-to-candidate timing delta."""

    percent = "n/a" if delta.delta_percent is None else f"{delta.delta_percent:+.1f}%"
    return (
        f"{delta.baseline_ms:.3f}->{delta.candidate_ms:.3f}ms "
        f"({delta.delta_ms:+.3f}ms, {percent})"
    )


__all__ = [
    "PromptAbuseComparisonReport",
    "PromptAbuseMetricDelta",
    "PromptAbuseScenarioComparison",
    "compare_report_files",
    "format_comparison",
    "write_comparison",
]

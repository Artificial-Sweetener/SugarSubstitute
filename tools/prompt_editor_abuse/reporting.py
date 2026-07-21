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

"""Serialize and summarize prompt-editor abuse campaign evidence."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from .models import PromptAbuseCampaignReport


def write_report(report: PromptAbuseCampaignReport, path: Path) -> None:
    """Write one stable machine-readable campaign report."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(report), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def format_summary(report: PromptAbuseCampaignReport) -> str:
    """Return a compact worst-first campaign summary."""

    header = (
        f"revision={report.revision} qt={report.qt_platform} "
        f"correct={report.correctness_passed} "
        f"structural={report.structural_performance_passed} "
        f"timing_target={report.timing_target_passed} "
        f"coverage={len(report.covered_operations)}/"
        f"{len(report.covered_operations) + len(report.missing_operations)}"
    )
    rows = [header]
    if report.structural_probe_enabled:
        rows.append("timing_confidence=instrumented")
    elif report.system_load is None:
        rows.append("timing_confidence=unmeasured")
    else:
        timing_confidence = (
            "representative" if report.timing_evidence_representative else "contended"
        )
        rows.append(
            "system_load="
            f"cpu={report.system_load.system_cpu_percent:.1f}% "
            f"harness={report.system_load.harness_cpu_percent:.1f}% "
            f"competing={report.system_load.competing_cpu_percent:.1f}% "
            f"timing_confidence={timing_confidence}"
        )
    if report.missing_operations:
        rows.append(f"missing_operations={report.missing_operations!r}")
    for result in sorted(
        report.results,
        key=lambda item: item.latency.p95_ms,
        reverse=True,
    ):
        rows.append(
            " ".join(
                (
                    result.scenario.name,
                    f"rep={result.repetition}",
                    f"p50={result.latency.p50_ms:.3f}ms",
                    f"p95={result.latency.p95_ms:.3f}ms",
                    f"p99={result.latency.p99_ms:.3f}ms",
                    f"max={result.latency.maximum_ms:.3f}ms",
                    f"settle={result.settle_ms:.3f}ms",
                    f"correct={result.correct}",
                    f"governed_samples={len(result.dispatch_samples)}",
                )
            )
        )
        if result.invariant_violations:
            rows.append(f"  violations={result.invariant_violations!r}")
        if result.structural_violations:
            rows.append(f"  structural_violations={result.structural_violations!r}")
        first_incorrect_sample = next(
            (
                sample
                for sample in result.dispatch_samples
                if (
                    not sample.source_exact
                    or not sample.caret_exact
                    or not sample.selection_exact
                    or not sample.feature_exact
                    or sample.visible_source_current_after_dispatch is False
                    or sample.visible_caret_current_after_dispatch is False
                    or sample.active_projection_ownership_valid is False
                    or sample.layout_projection_ownership_valid is False
                    or sample.layout_fragment_ownership_valid is False
                    or sample.caret_transform_depth_valid is False
                )
            ),
            None,
        )
        if first_incorrect_sample is not None:
            action = result.scenario.actions[first_incorrect_sample.action_index]
            expected_source = action.expected_source
            actual_source = first_incorrect_sample.actual_source_on_mismatch
            mismatch_index = (
                None
                if expected_source is None or actual_source is None
                else _first_mismatch_index(expected_source, actual_source)
            )
            rows.append(
                "  first_incorrect="
                f"a{first_incorrect_sample.action_index}/"
                f"u{first_incorrect_sample.unit_index} "
                f"{first_incorrect_sample.label} "
                f"mismatch_index={mismatch_index} "
                f"actual_cursor={first_incorrect_sample.actual_cursor_position} "
                f"expected_cursor={first_incorrect_sample.expected_cursor_position} "
                f"actual_anchor={first_incorrect_sample.actual_anchor_position} "
                f"expected_anchor={first_incorrect_sample.expected_anchor_position} "
                f"feature_mismatch={first_incorrect_sample.feature_mismatch!r}"
                f" layout_fragment_mismatch="
                f"{first_incorrect_sample.layout_fragment_ownership_mismatch!r}"
            )
        if result.latency_breakdown is not None:
            breakdown = result.latency_breakdown
            rows.append(
                "  latency_lanes="
                f"text_p95={breakdown.text_input.p95_ms:.3f}ms/"
                f"n={breakdown.text_input_count} "
                f"interaction_p95={breakdown.interaction.p95_ms:.3f}ms/"
                f"n={breakdown.interaction_count} "
                f"lifecycle_p95={breakdown.lifecycle.p95_ms:.3f}ms/"
                f"n={breakdown.lifecycle_count} "
                f"drain_p95={breakdown.backlog_drain.p95_ms:.3f}ms/"
                f"n={breakdown.backlog_drain_count}"
            )
        slowest_samples = sorted(
            result.dispatch_samples,
            key=lambda sample: sample.dispatch_ms,
            reverse=True,
        )[:5]
        if slowest_samples:
            rows.append(
                "  slowest="
                + ", ".join(
                    (
                        f"a{sample.action_index}/u{sample.unit_index} "
                        f"{sample.label}={sample.dispatch_ms:.3f}ms "
                        f"cpu={_optional_milliseconds(sample.dispatch_thread_cpu_ms)} "
                        f"source={sample.source_exact} caret={sample.caret_exact} "
                        f"selection={sample.selection_exact} "
                        f"feature={sample.feature_exact} "
                        f"visible={sample.visible_source_current_after_dispatch} "
                        f"visual_caret={sample.visible_caret_current_after_dispatch} "
                        f"active_owner={sample.active_projection_ownership_valid} "
                        f"layout_owner={sample.layout_projection_ownership_valid} "
                        f"fragment_owner={sample.layout_fragment_ownership_valid} "
                        f"caret_transform_depth={sample.caret_transform_depth} "
                        f"caret_depth_valid={sample.caret_transform_depth_valid} "
                        f"overlay={sample.transient_overlay_kind} "
                        f"freshness={sample.projection_freshness} "
                        f"projection={sample.projection_current_after_dispatch} "
                        f"semantic={sample.semantic_current_after_dispatch} "
                        f"alloc_blocks={sample.allocated_block_delta} "
                        f"gc={sample.gc_collection_count}/"
                        f"{sample.gc_pause_ms:.3f}ms/"
                        f"{sample.gc_collected_objects}obj"
                    )
                    for sample in slowest_samples
                )
            )
        action_owner_work = tuple(
            (
                action_delta,
                tuple(
                    (name, value)
                    for name, value in action_delta.counter_deltas
                    if name.endswith("_count") and value != 0.0
                ),
            )
            for action_delta in result.action_owner_deltas
            if any(
                name.endswith("_count") and value != 0.0
                for name, value in action_delta.counter_deltas
            )
        )
        if action_owner_work:
            rows.append(
                "  action_owner_work="
                + "; ".join(
                    f"a{action_delta.action_index}/u{action_delta.unit_index} "
                    f"{action_delta.label} "
                    + ",".join(f"{name}={value:g}" for name, value in counters[:8])
                    for action_delta, counters in action_owner_work[:8]
                )
            )
        owner_counter_resets = tuple(
            action_delta
            for action_delta in result.action_owner_deltas
            if action_delta.reset_counter_names
        )
        if owner_counter_resets:
            rows.append(
                "  action_owner_counter_resets="
                + "; ".join(
                    f"a{action_delta.action_index}/u{action_delta.unit_index} "
                    f"{action_delta.label} "
                    + ",".join(action_delta.reset_counter_names[:8])
                    for action_delta in owner_counter_resets[:8]
                )
            )
        if result.actual_text_on_mismatch is not None:
            mismatch_index = _first_mismatch_index(
                result.scenario.expected_text,
                result.actual_text_on_mismatch,
            )
            rows.append(
                "  source_mismatch="
                f"index={mismatch_index} "
                f"expected_length={len(result.scenario.expected_text)} "
                f"actual_length={len(result.actual_text_on_mismatch)}"
            )
        if result.diagnostics is not None:
            diagnostics = result.diagnostics
            rows.append(
                "  projection="
                f"rebuilds={diagnostics.canonical_rebuild_count} "
                f"paths={dict(diagnostics.apply_path_counts)!r} "
                f"incremental_rejections="
                f"{dict(diagnostics.incremental_rejection_counts)!r} "
                f"layout_rejections={dict(diagnostics.layout_rejection_counts)!r}"
            )
            rows.append(
                "  cumulative_hotspots="
                + ", ".join(
                    f"{hotspot.function}={hotspot.cumulative_time_ms:.3f}ms"
                    for hotspot in diagnostics.hotspots[:5]
                )
            )
            self_hotspots = sorted(
                diagnostics.hotspots,
                key=lambda item: item.own_time_ms,
                reverse=True,
            )[:10]
            rows.append(
                "  self_hotspots="
                + ", ".join(
                    f"{hotspot.function}={hotspot.own_time_ms:.3f}ms"
                    for hotspot in self_hotspots
                )
            )
            if self_hotspots and self_hotspots[0].callers:
                rows.append(
                    "  hottest_self_callers=" + ", ".join(self_hotspots[0].callers)
                )
            action_profiles_by_index = {
                profile.action_index: profile for profile in diagnostics.action_profiles
            }
            profiled_action_indices = tuple(
                dict.fromkeys(sample.action_index for sample in slowest_samples)
            )
            for profiled_action_index in profiled_action_indices[:3]:
                action_profile = action_profiles_by_index.get(profiled_action_index)
                if action_profile is None:
                    continue
                rows.append(
                    f"  action_profile=a{action_profile.action_index} "
                    f"{action_profile.label} "
                    + ", ".join(
                        f"{hotspot.function}={hotspot.cumulative_time_ms:.3f}ms"
                        for hotspot in action_profile.hotspots[:5]
                    )
                )
            if diagnostics.owner_counters:
                rows.append(
                    "  owner_counters="
                    + ", ".join(
                        f"{name}={value:g}"
                        for name, value in diagnostics.owner_counters
                    )
                )
            slowest_freshness = sorted(
                diagnostics.freshness_samples,
                key=lambda item: item.fully_current_ms,
                reverse=True,
            )[:5]
            if slowest_freshness:
                rows.append(
                    "  publication="
                    + ", ".join(
                        f"a{sample.action_index} {sample.label} "
                        f"projection={sample.projection_ms:.3f}ms "
                        f"semantic={sample.semantic_ms:.3f}ms "
                        f"timeout={sample.timed_out}"
                        for sample in slowest_freshness
                    )
                )
    return "\n".join(rows)


def _optional_milliseconds(value: float | None) -> str:
    """Format optional timing evidence without inventing unavailable samples."""

    return "n/a" if value is None else f"{value:.3f}ms"


def _first_mismatch_index(expected: str, actual: str) -> int:
    """Return the first differing source index or the shared source length."""

    for index, (expected_character, actual_character) in enumerate(
        zip(expected, actual, strict=False)
    ):
        if expected_character != actual_character:
            return index
    return min(len(expected), len(actual))


__all__ = ["format_summary", "write_report"]

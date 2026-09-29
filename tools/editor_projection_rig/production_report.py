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

"""Aggregate production editor trace measurements and correctness budgets."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any


def budget_summary(
    iteration_reports: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Return pass/fail correctness budgets for production trace reports."""

    signature_mismatches = sum(
        0 if bool(report.get("signature_matched")) else 1
        for report in iteration_reports
    )
    parent_violations = sum(
        len(report.get("parent_chain_violations", ()))
        if isinstance(report.get("parent_chain_violations"), list)
        else 0
        for report in iteration_reports
    )
    incomplete = sum(
        0 if bool(report.get("projection_completed")) else 1
        for report in iteration_reports
    )
    partial_orphans = sum(
        len(report.get("partial_orphan_field_cards", ()))
        if isinstance(report.get("partial_orphan_field_cards"), list)
        else 0
        for report in iteration_reports
    )
    return {
        "projection_incomplete": _zero_budget(incomplete),
        "partial_orphan_field_cards": _zero_budget(partial_orphans),
        "settled_signature_mismatches": _zero_budget(signature_mismatches),
        "parenting.violations": _zero_budget(parent_violations),
    }


def aggregate_summary(
    iteration_reports: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Return scenario-grouped timing and work-counter summaries."""

    grouped_reports: dict[str, list[Mapping[str, Any]]] = {}
    for report in iteration_reports:
        scenario_id = str(report.get("scenario_id", ""))
        grouped_reports.setdefault(scenario_id, []).append(report)
    return {
        scenario_id: _aggregate_scenario_reports(reports)
        for scenario_id, reports in sorted(grouped_reports.items())
    }


def _zero_budget(actual: int) -> dict[str, int | bool]:
    """Return a zero-tolerance correctness budget result."""

    return {"actual": actual, "limit": 0, "passed": actual == 0}


def _aggregate_scenario_reports(
    reports: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Aggregate one scenario's timings and counters."""

    return {
        "iterations": len(reports),
        "timings_ms": _aggregate_numeric_mapping(reports, key="timings_ms"),
        "counter_totals": _sum_numeric_mapping(reports, key="counters"),
    }


def _aggregate_numeric_mapping(
    reports: Sequence[Mapping[str, Any]],
    *,
    key: str,
) -> dict[str, Any]:
    """Aggregate numeric values from nested report mappings."""

    values_by_name: dict[str, list[float]] = {}
    for report in reports:
        values = report.get(key, {})
        if not isinstance(values, Mapping):
            continue
        for name, value in values.items():
            if isinstance(value, int | float):
                values_by_name.setdefault(str(name), []).append(float(value))
    return {
        name: _numeric_stats(values) for name, values in sorted(values_by_name.items())
    }


def _sum_numeric_mapping(
    reports: Sequence[Mapping[str, Any]],
    *,
    key: str,
) -> dict[str, float]:
    """Sum numeric values from nested report mappings."""

    totals: dict[str, float] = {}
    for report in reports:
        values = report.get(key, {})
        if not isinstance(values, Mapping):
            continue
        for name, value in values.items():
            if isinstance(value, int | float):
                totals[str(name)] = totals.get(str(name), 0.0) + float(value)
    return dict(sorted(totals.items()))


def _numeric_stats(values: Sequence[float]) -> dict[str, float]:
    """Return deterministic min/mean/p95/max statistics."""

    ordered = sorted(values)
    if not ordered:
        return {"min": 0.0, "mean": 0.0, "p95": 0.0, "max": 0.0}
    p95_index = max(0, math.ceil(len(ordered) * 0.95) - 1)
    return {
        "min": round(ordered[0], 3),
        "mean": round(sum(ordered) / len(ordered), 3),
        "p95": round(ordered[p95_index], 3),
        "max": round(ordered[-1], 3),
    }

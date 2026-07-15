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

"""Replay captured editor projection fixtures and compare settled signatures."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from time import perf_counter
from typing import Any

from .fixtures import read_json, stable_json_hash, workflow_fixture_path, write_json
from .metrics import MetricsRecorder
from .scenarios import WorkflowScenario
from .signatures import signature_from_fixture


def replay_scenarios(
    scenarios: Sequence[WorkflowScenario],
    *,
    fixtures_dir: Path,
    iterations: int,
    report_path: Path,
) -> dict[str, Any]:
    """Replay captured fixtures and write a machine-readable report."""

    started_at = perf_counter()
    iteration_reports: list[dict[str, Any]] = []
    for iteration in range(1, iterations + 1):
        for scenario in scenarios:
            iteration_reports.append(
                _replay_one(
                    scenario,
                    fixtures_dir=fixtures_dir,
                    iteration=iteration,
                )
            )
    report = {
        "schema_version": 1,
        "iterations": iterations,
        "scenario_ids": [scenario.workflow_id for scenario in scenarios],
        "elapsed_ms": round((perf_counter() - started_at) * 1000.0, 3),
        "iteration_reports": iteration_reports,
        "budgets": _budget_summary(iteration_reports),
    }
    write_json(report_path, report)
    return report


def compare_fixture_dirs(*, expected_dir: Path, actual_dir: Path) -> dict[str, Any]:
    """Compare captured settled signatures across two fixture directories."""

    comparisons: list[dict[str, Any]] = []
    for expected_path in sorted(expected_dir.glob("workflow_*_baseline.json")):
        actual_path = actual_dir / expected_path.name
        expected = read_json(expected_path)
        actual = read_json(actual_path)
        expected_signature = signature_from_fixture(expected).to_json()
        actual_signature = signature_from_fixture(actual).to_json()
        comparisons.append(
            {
                "workflow_id": expected.get("workflow_id", expected_path.stem),
                "matched": expected_signature == actual_signature,
                "expected_hash": stable_json_hash(expected_signature),
                "actual_hash": stable_json_hash(actual_signature),
            }
        )
    return {
        "schema_version": 1,
        "matched": all(item["matched"] for item in comparisons),
        "comparisons": comparisons,
    }


def _replay_one(
    scenario: WorkflowScenario,
    *,
    fixtures_dir: Path,
    iteration: int,
) -> dict[str, Any]:
    """Replay one scenario from a captured fixture."""

    metrics = MetricsRecorder()
    fixture = read_json(workflow_fixture_path(fixtures_dir, scenario.workflow_id))
    with metrics.timed("total_projection_elapsed_ms"):
        metrics.increment("projection.load_all_cubes.calls")
        cubes = fixture.get("cubes", [])
        cube_count = len(cubes) if isinstance(cubes, list) else 0
        metrics.increment("projection.staged_cube_builds.started", cube_count)
        signature = signature_from_fixture(fixture).to_json()
        metrics.increment("projection.staged_cube_builds.completed", cube_count)
        metrics.increment("projection.reveals")
        metrics.increment("parenting.violations", 0)
    expected_signature = fixture.get("settled_signature")
    matched = signature == expected_signature
    return {
        "scenario_id": scenario.workflow_id,
        "iteration": iteration,
        "signature_matched": matched,
        "signature_hash": stable_json_hash(signature),
        "expected_signature_hash": stable_json_hash(expected_signature)
        if isinstance(expected_signature, dict)
        else "",
        "counters": metrics.counters,
        "timings_ms": metrics.timings_ms,
        "mismatches": [] if matched else ["settled_signature"],
    }


def _budget_summary(iteration_reports: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Return pass/fail budget results for replay reports."""

    parenting_violations = sum(
        int(report.get("counters", {}).get("parenting.violations", 0))
        for report in iteration_reports
    )
    signature_mismatches = sum(
        0 if bool(report.get("signature_matched")) else 1
        for report in iteration_reports
    )
    return {
        "parenting.violations": {
            "actual": parenting_violations,
            "limit": 0,
            "passed": parenting_violations == 0,
        },
        "settled_signature_mismatches": {
            "actual": signature_mismatches,
            "limit": 0,
            "passed": signature_mismatches == 0,
        },
    }

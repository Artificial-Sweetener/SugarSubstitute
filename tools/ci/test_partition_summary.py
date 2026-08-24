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

"""Own structured timing and artifact evidence for fresh-process partitions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

from tools.ci.test_module_process import TestModuleRun, junit_path_for_module


class TestModuleEvidence(TypedDict):
    """Describe one terminal fresh-process module in portable JSON fields."""

    module_path: str
    passed: bool
    return_code: int
    started_at_utc: str
    duration_seconds: float
    runner_slot: str
    junit_path: str
    failure_artifact_path: str | None


class TestPartitionEvidence(TypedDict):
    """Describe one complete isolated or serial execution partition."""

    schema_version: int
    lane: str
    worker_count: int
    module_count: int
    passed_count: int
    failed_count: int
    duration_seconds: float
    modules: list[TestModuleEvidence]


def write_test_partition_summary(
    *,
    junit_directory: Path,
    lane: str,
    worker_count: int,
    duration_seconds: float,
    runs: tuple[TestModuleRun, ...],
) -> Path:
    """Write one deterministic summary beside the partition's JUnit evidence."""

    ordered_runs = tuple(sorted(runs, key=lambda run: run.module_path))
    evidence = TestPartitionEvidence(
        schema_version=1,
        lane=lane,
        worker_count=worker_count,
        module_count=len(ordered_runs),
        passed_count=sum(run.passed for run in ordered_runs),
        failed_count=sum(not run.passed for run in ordered_runs),
        duration_seconds=duration_seconds,
        modules=[
            _module_evidence(junit_directory=junit_directory, run=run)
            for run in ordered_runs
        ],
    )
    summary_path = junit_directory / "execution-summary.json"
    summary_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary_path


def _module_evidence(
    *,
    junit_directory: Path,
    run: TestModuleRun,
) -> TestModuleEvidence:
    """Translate one in-memory result into result-root-relative evidence."""

    return TestModuleEvidence(
        module_path=run.module_path,
        passed=run.passed,
        return_code=run.return_code,
        started_at_utc=run.started_at_utc,
        duration_seconds=run.duration_seconds,
        runner_slot=run.runner_slot,
        junit_path=junit_path_for_module(
            junit_directory,
            run.module_path,
        )
        .relative_to(junit_directory)
        .as_posix(),
        failure_artifact_path=_relative_artifact_path(
            junit_directory=junit_directory,
            artifact_path=run.failure_artifact_path,
        ),
    )


def _relative_artifact_path(
    *,
    junit_directory: Path,
    artifact_path: Path | None,
) -> str | None:
    """Return a portable artifact path without exposing runner-local roots."""

    if artifact_path is None:
        return None
    return artifact_path.relative_to(junit_directory).as_posix()


__all__ = [
    "TestModuleEvidence",
    "TestPartitionEvidence",
    "write_test_partition_summary",
]

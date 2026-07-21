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

"""Orchestrate repeatable production-mounted prompt-editor abuse campaigns."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
import subprocess
from typing import Protocol

from .coverage import capture_operation_coverage
from .models import (
    PromptAbuseCampaignReport,
    PromptAbuseScenario,
    PromptAbuseScenarioResult,
)
from .system_load import PromptAbuseSystemLoadProbe
from .structural_instrumentation import prompt_abuse_structural_instrumentation


class ScenarioRunner(Protocol):
    """Run one scenario repetition through a concrete editor driver."""

    def __call__(
        self,
        scenario: PromptAbuseScenario,
        /,
        *,
        repetition: int,
        artifact_root: Path,
        deep_trace: bool,
    ) -> PromptAbuseScenarioResult:
        """Return measured evidence for one scenario repetition."""

        ...


def run_campaign(
    scenarios: Sequence[PromptAbuseScenario],
    *,
    repetitions: int,
    seed: int,
    frame_budget_ms: float,
    artifact_root: Path,
    deep_trace: bool = False,
    structural_probe: bool = False,
    scenario_runner: ScenarioRunner | None = None,
    platform_name: Callable[[], str] | None = None,
) -> PromptAbuseCampaignReport:
    """Run scenarios repeatedly and return reproducible campaign evidence."""

    if repetitions < 1:
        raise ValueError("Prompt abuse repetitions must be positive.")
    if frame_budget_ms <= 0:
        raise ValueError("Prompt abuse frame budget must be positive.")
    artifact_root.mkdir(parents=True, exist_ok=True)
    if scenario_runner is None or platform_name is None:
        from .real_shell_driver import qt_platform_name, run_real_shell_scenario

        scenario_runner = scenario_runner or run_real_shell_scenario
        platform_name = platform_name or qt_platform_name
    system_load_probe = PromptAbuseSystemLoadProbe()
    with prompt_abuse_structural_instrumentation(enabled=structural_probe):
        results = tuple(
            scenario_runner(
                scenario,
                repetition=repetition,
                artifact_root=artifact_root,
                deep_trace=deep_trace,
            )
            for scenario in scenarios
            for repetition in range(repetitions)
        )
    coverage = capture_operation_coverage(tuple(scenarios))
    return PromptAbuseCampaignReport(
        revision=_git_revision(),
        qt_platform=platform_name(),
        seed=seed,
        frame_budget_ms=frame_budget_ms,
        results=results,
        covered_operations=coverage.covered,
        missing_operations=coverage.missing,
        system_load=system_load_probe.finish(),
        structural_probe_enabled=structural_probe,
    )


def _git_revision() -> str:
    """Return the current Git revision without mutating repository state."""

    completed = subprocess.run(  # noqa: S603
        ["git", "rev-parse", "--short", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    if completed.returncode != 0:
        return "unknown"
    return completed.stdout.strip() or "unknown"


__all__ = ["ScenarioRunner", "run_campaign"]

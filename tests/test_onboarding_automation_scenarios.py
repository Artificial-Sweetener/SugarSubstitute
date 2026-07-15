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

"""Exercise the onboarding automation harness against deterministic UI scenarios."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from tests.onboarding_automation import scenario_runner
from tests.onboarding_automation.fixture_paths import resolve_scenario_paths
from tests.onboarding_automation.scenarios import build_scenarios

_SERIAL_UI_AUTOMATION_ONLY = pytest.mark.skipif(
    bool(os.environ.get("PYTEST_XDIST_WORKER")),
    reason="real onboarding automation scenarios require non-xdist execution on Windows",
)


@_SERIAL_UI_AUTOMATION_ONLY
def test_scenario_runner_executes_managed_ui_smoke_scenario(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The harness should drive the managed-local onboarding UI to completion."""

    exit_code = scenario_runner.main(["--scenario", "ui_smoke_managed"])

    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert exit_code == 0
    assert result["success"] is True
    assert result["current_page"] == "OnboardingCompletionPage"
    assert Path(result["screenshot_dir"], "welcome.png").exists()
    assert Path(result["screenshot_dir"], "completion.png").exists()


@_SERIAL_UI_AUTOMATION_ONLY
def test_scenario_runner_executes_attached_ui_smoke_scenario(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The harness should also drive the attached-local onboarding UI path."""

    exit_code = scenario_runner.main(["--scenario", "ui_smoke_attached"])

    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert exit_code == 0
    assert result["success"] is True
    assert result["current_page"] == "OnboardingCompletionPage"
    assert Path(result["screenshot_dir"], "target_mode.png").exists()
    assert Path(result["screenshot_dir"], "attached_local.png").exists()


def test_scenario_catalog_includes_failure_and_recovery_coverage() -> None:
    """The harness scenario catalog should expose the campaign's real failure matrix runs."""

    scenarios = build_scenarios(resolve_scenario_paths())

    assert "managed_stale_bootstrap_recovery_real" in scenarios
    assert "managed_clone_failure_real" in scenarios
    assert "managed_retry_after_clone_failure_real" in scenarios
    assert "managed_dependency_failure_real" in scenarios
    assert "attached_missing_workspace_real" in scenarios
    assert "attached_unreachable_real" in scenarios

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

"""Drive deterministic mounted onboarding scenarios through the runner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.onboarding_automation import scenario_runner


def test_scenario_runner_executes_managed_ui_smoke_scenario(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """Drive the managed-local onboarding UI to completion."""

    exit_code = scenario_runner.main(
        ["--scenario", "ui_smoke_managed"],
        run_root=tmp_path,
    )

    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert exit_code == 0
    assert result["success"] is True
    assert result["current_page"] == "OnboardingCompletionPage"
    assert Path(result["screenshot_dir"], "welcome.png").exists()
    assert Path(result["screenshot_dir"], "completion.png").exists()


def test_scenario_runner_executes_attached_ui_smoke_scenario(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """Drive the attached-local onboarding UI to completion."""

    exit_code = scenario_runner.main(
        ["--scenario", "ui_smoke_attached"],
        run_root=tmp_path,
    )

    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert exit_code == 0
    assert result["success"] is True
    assert result["current_page"] == "OnboardingCompletionPage"
    assert Path(result["screenshot_dir"], "target_mode.png").exists()
    assert Path(result["screenshot_dir"], "attached_local.png").exists()

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

"""Verify weighted-token actions after production-owned workflow restore paths."""

from __future__ import annotations

from pathlib import Path

from tools.prompt_editor_abuse.emphasis_workloads import emphasis_scenarios
from tools.prompt_editor_abuse.real_shell_driver import run_real_shell_scenario


def test_restored_prompt_weight_pointer_matrix(tmp_path: Path) -> None:
    """Cache and PNG restores must preserve arrows and exact weight editing."""

    restored_scenarios = tuple(
        scenario
        for scenario in emphasis_scenarios()
        if scenario.mount_source != "fresh"
    )

    results = tuple(
        run_real_shell_scenario(
            scenario,
            repetition=0,
            artifact_root=tmp_path,
        )
        for scenario in restored_scenarios
    )

    failures = tuple(
        (result.scenario.name, result.invariant_violations)
        for result in results
        if not result.correct
    )
    assert len(results) == 12
    assert failures == ()

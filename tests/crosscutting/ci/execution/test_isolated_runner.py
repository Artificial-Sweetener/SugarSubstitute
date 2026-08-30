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

"""Verify bounded concurrency for independent fresh-process test modules."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from tools.ci import run_isolated_test_modules as isolated_runner
from tools.ci.test_module_process import TestModuleRun as ModuleRun


def test_isolated_runner_overlaps_modules_and_reports_all_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use the qualified worker bound without sharing child process state."""

    lock = threading.Lock()
    overlap_reached = threading.Event()
    active = 0
    maximum_active = 0
    observed_temp_roots: list[Path] = []

    def run_module(
        *,
        project_root: Path,
        module_path: str,
        junit_directory: Path,
        base_temp_root: Path,
    ) -> ModuleRun:
        """Hold the first pair until concurrent execution is observable."""

        nonlocal active, maximum_active
        assert project_root == tmp_path
        assert junit_directory == tmp_path / "results"
        assert base_temp_root.is_dir()
        observed_temp_roots.append(base_temp_root)
        with lock:
            active += 1
            maximum_active = max(maximum_active, active)
            if active == 2:
                overlap_reached.set()
        assert overlap_reached.wait(timeout=2.0)
        with lock:
            active -= 1
        return ModuleRun(
            module_path=module_path,
            return_code=1 if module_path.endswith(("b.py", "c.py")) else 0,
            output=f"output for {module_path}",
            started_at_utc="2026-08-24T00:00:00+00:00",
            duration_seconds=1.25,
            runner_slot="isolated-test-module_0",
        )

    monkeypatch.setattr(isolated_runner, "run_test_module", run_module)

    failures = isolated_runner.run_isolated_test_modules(
        project_root=tmp_path,
        junit_directory=tmp_path / "results",
        module_paths=("tests/test_a.py", "tests/test_b.py", "tests/test_c.py"),
        available_workers=2,
    )

    assert maximum_active == 2
    assert len(set(observed_temp_roots)) == 1
    assert not observed_temp_roots[0].exists()
    assert failures == ("tests/test_b.py", "tests/test_c.py")
    summary = json.loads(
        (tmp_path / "results/execution-summary.json").read_text(encoding="utf-8")
    )
    assert summary["lane"] == "isolated"
    assert summary["worker_count"] == 2
    assert summary["module_count"] == 3
    assert summary["passed_count"] == 1
    assert summary["failed_count"] == 2
    assert [module["module_path"] for module in summary["modules"]] == [
        "tests/test_a.py",
        "tests/test_b.py",
        "tests/test_c.py",
    ]
    assert {module["runner_slot"] for module in summary["modules"]} == {
        "isolated-test-module_0"
    }

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

"""Verify genuinely sequential execution of globally exclusive test modules."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.ci import run_serial_test_modules as serial_runner
from tools.ci.test_module_process import TestModuleRun as ModuleRun


def test_serial_runner_preserves_order_and_continues_after_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run every exclusive module sequentially and report every failure."""

    calls: list[str] = []
    observed_temp_roots: list[Path] = []

    def run_module(
        *,
        project_root: Path,
        module_path: str,
        junit_directory: Path,
        base_temp_root: Path,
    ) -> ModuleRun:
        """Record one sequential invocation and fail the middle module."""

        assert project_root == tmp_path
        assert junit_directory == tmp_path / "results"
        assert base_temp_root.is_dir()
        observed_temp_roots.append(base_temp_root)
        calls.append(module_path)
        return ModuleRun(
            module_path=module_path,
            return_code=1 if module_path == "tests/test_b.py" else 0,
            output="failure details",
        )

    monkeypatch.setattr(serial_runner, "run_test_module", run_module)

    failures = serial_runner.run_serial_test_modules(
        project_root=tmp_path,
        junit_directory=tmp_path / "results",
        module_paths=("tests/test_a.py", "tests/test_b.py", "tests/test_c.py"),
    )

    assert calls == ["tests/test_a.py", "tests/test_b.py", "tests/test_c.py"]
    assert len(set(observed_temp_roots)) == 1
    assert not observed_temp_roots[0].exists()
    assert failures == ("tests/test_b.py",)

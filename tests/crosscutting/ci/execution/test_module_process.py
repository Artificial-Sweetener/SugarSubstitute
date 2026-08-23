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

"""Verify one module's shared fresh-process execution boundary."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tools.ci import test_module_process


def test_junit_path_for_module_is_collision_free() -> None:
    """Preserve the complete repository path in each JUnit filename."""

    assert test_module_process.junit_path_for_module(
        Path("results"),
        "tests/presentation/test_widget.py",
    ) == Path("results/tests__presentation__test_widget.xml")


def test_build_test_module_command_uses_fresh_non_xdist_process() -> None:
    """Execute one module without xdist and with isolated result paths."""

    command = test_module_process.build_test_module_command(
        module_path="tests/test_widget.py",
        junit_path=Path("results/widget.xml"),
        base_temp=Path("temp/widget"),
    )

    assert command == (
        sys.executable,
        "-m",
        "pytest",
        "-n",
        "0",
        "-q",
        "tests/test_widget.py",
        f"--junitxml={Path('results/widget.xml')}",
        f"--basetemp={Path('temp/widget')}",
    )


def test_prepare_module_base_temp_creates_required_parent(tmp_path: Path) -> None:
    """Create pytest's parent directory before giving it a nested base temp."""

    base_temp_root = tmp_path / "module-run"
    base_temp = test_module_process.prepare_module_base_temp(
        base_temp_root=base_temp_root,
        junit_path=Path("results/tests__test_widget.xml"),
    )

    assert base_temp == base_temp_root / "tests__test_widget"
    assert base_temp.parent.is_dir()
    assert not base_temp.exists()


def test_run_test_module_reports_timeout_with_captured_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Turn a stuck child into a terminal diagnostic result."""

    def timeout(*_args: object, **_kwargs: object) -> None:
        """Raise the subprocess timeout produced by a stuck pytest child."""

        raise subprocess.TimeoutExpired(
            cmd=(sys.executable, "-m", "pytest"),
            timeout=7,
            output=b"last child output",
        )

    monkeypatch.setattr(subprocess, "run", timeout)

    result = test_module_process.run_test_module(
        project_root=tmp_path,
        module_path="tests/test_stuck.py",
        junit_directory=tmp_path / "results",
        base_temp_root=tmp_path / "temp",
        timeout_seconds=7,
    )

    assert result.return_code == 124
    assert not result.passed
    assert "exceeded 7 seconds" in result.output
    assert "last child output" in result.output

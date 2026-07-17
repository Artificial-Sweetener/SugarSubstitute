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

"""Verify isolated execution of serial CI test modules."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from tools.ci import run_serial_test_modules as serial_runner


def test_junit_path_for_module_is_collision_free() -> None:
    """Preserve the complete repository path in each JUnit filename."""

    assert serial_runner.junit_path_for_module(
        Path("results"),
        "tests/presentation/test_widget.py",
    ) == Path("results/tests__presentation__test_widget.xml")


def test_build_serial_test_command_uses_fresh_non_xdist_process() -> None:
    """Execute one module without xdist and with isolated result paths."""

    command = serial_runner.build_serial_test_command(
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

    base_temp = serial_runner.prepare_module_base_temp(
        project_root=tmp_path,
        junit_path=Path("results/tests__test_widget.xml"),
    )

    assert base_temp == tmp_path / ".pytest-tmp/serial/tests__test_widget"
    assert base_temp.parent.is_dir()
    assert not base_temp.exists()


def test_run_serial_test_modules_continues_after_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Report every failing module instead of stopping at the first failure."""

    calls: list[str] = []

    def run_module(
        *,
        project_root: Path,
        module_path: str,
        junit_directory: Path,
    ) -> int:
        """Record one isolated module invocation and fail the middle module."""

        assert project_root == tmp_path
        assert junit_directory == tmp_path / "results"
        calls.append(module_path)
        return 1 if module_path == "tests/test_b.py" else 0

    monkeypatch.setattr(serial_runner, "run_serial_test_module", run_module)

    failures = serial_runner.run_serial_test_modules(
        project_root=tmp_path,
        junit_directory=tmp_path / "results",
        module_paths=("tests/test_a.py", "tests/test_b.py", "tests/test_c.py"),
    )

    assert calls == ["tests/test_a.py", "tests/test_b.py", "tests/test_c.py"]
    assert failures == ("tests/test_b.py",)

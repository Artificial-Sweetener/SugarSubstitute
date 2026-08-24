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

"""Own fresh-process execution of one classified pytest module."""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from dataclasses import dataclass
from pathlib import Path
from shutil import copytree, rmtree
from threading import current_thread
from time import perf_counter


MODULE_TIMEOUT_SECONDS = 600


@dataclass(frozen=True, slots=True)
class TestModuleRun:
    """Describe the terminal result of one fresh pytest process."""

    module_path: str
    return_code: int
    output: str
    started_at_utc: str = ""
    duration_seconds: float = 0.0
    runner_slot: str = "unknown"
    failure_artifact_path: Path | None = None

    @property
    def passed(self) -> bool:
        """Return whether pytest completed successfully."""

        return self.return_code == 0


def junit_path_for_module(junit_directory: Path, module_path: str) -> Path:
    """Return one collision-free JUnit path for a repository test module."""

    filename = module_path.removesuffix(".py").replace("/", "__") + ".xml"
    return junit_directory / filename


def build_test_module_command(
    *,
    module_path: str,
    junit_path: Path,
    base_temp: Path,
) -> tuple[str, ...]:
    """Build one non-xdist pytest command with isolated artifact paths."""

    return (
        sys.executable,
        "-m",
        "pytest",
        "-n",
        "0",
        "-q",
        module_path,
        f"--junitxml={junit_path}",
        f"--basetemp={base_temp}",
    )


def prepare_module_base_temp(
    *,
    base_temp_root: Path,
    junit_path: Path,
) -> Path:
    """Create and return the parent-owned base-temp path for one module."""

    base_temp_root.mkdir(parents=True, exist_ok=True)
    return base_temp_root / junit_path.stem


def run_test_module(
    *,
    project_root: Path,
    module_path: str,
    junit_directory: Path,
    base_temp_root: Path,
    timeout_seconds: int = MODULE_TIMEOUT_SECONDS,
) -> TestModuleRun:
    """Run one module in a fresh process and capture actionable output."""

    started_at_utc = datetime.now(UTC).isoformat()
    started_at = perf_counter()
    runner_slot = current_thread().name
    junit_path = junit_path_for_module(junit_directory, module_path)
    base_temp = prepare_module_base_temp(
        base_temp_root=base_temp_root,
        junit_path=junit_path,
    )
    command = build_test_module_command(
        module_path=module_path,
        junit_path=junit_path,
        base_temp=base_temp,
    )
    try:
        completed = subprocess.run(  # noqa: S603
            command,
            cwd=project_root,
            check=False,
            timeout=timeout_seconds,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired as error:
        captured_output = error.stdout or ""
        if isinstance(captured_output, bytes):
            captured_output = captured_output.decode("utf-8", errors="replace")
        return _terminal_run(
            module_path=module_path,
            return_code=124,
            output=(
                f"Fresh pytest process exceeded {timeout_seconds} seconds.\n"
                f"{captured_output}"
            ),
            started_at_utc=started_at_utc,
            started_at=started_at,
            runner_slot=runner_slot,
            base_temp=base_temp,
            junit_directory=junit_directory,
            junit_path=junit_path,
        )
    return _terminal_run(
        module_path=module_path,
        return_code=completed.returncode,
        output=completed.stdout,
        started_at_utc=started_at_utc,
        started_at=started_at,
        runner_slot=runner_slot,
        base_temp=base_temp,
        junit_directory=junit_directory,
        junit_path=junit_path,
    )


def _terminal_run(
    *,
    module_path: str,
    return_code: int,
    output: str,
    started_at_utc: str,
    started_at: float,
    runner_slot: str,
    base_temp: Path,
    junit_directory: Path,
    junit_path: Path,
) -> TestModuleRun:
    """Build one result after preserving any failed module-owned artifacts."""

    artifact_path = None
    if return_code != 0:
        try:
            artifact_path = _preserve_failure_artifacts(
                base_temp=base_temp,
                destination=junit_directory / "failure-artifacts" / junit_path.stem,
            )
        except OSError as error:
            output = (
                f"{output}\nCould not preserve failed-module artifacts: "
                f"{type(error).__name__}: {error}"
            )
    return TestModuleRun(
        module_path=module_path,
        return_code=return_code,
        output=output,
        started_at_utc=started_at_utc,
        duration_seconds=perf_counter() - started_at,
        runner_slot=runner_slot,
        failure_artifact_path=artifact_path,
    )


def _preserve_failure_artifacts(*, base_temp: Path, destination: Path) -> Path | None:
    """Copy failed-module temporary evidence into the persistent result owner."""

    if not base_temp.is_dir():
        return None
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        rmtree(destination)
    copytree(base_temp, destination)
    return destination


__all__ = [
    "MODULE_TIMEOUT_SECONDS",
    "TestModuleRun",
    "build_test_module_command",
    "junit_path_for_module",
    "prepare_module_base_temp",
    "run_test_module",
]

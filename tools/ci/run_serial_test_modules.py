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

"""Run every serial test module in an isolated pytest process."""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from tests.ci_test_policy import SERIAL_TEST_MODULES


_LOGGER = logging.getLogger(__name__)
_MODULE_TIMEOUT_SECONDS = 600


def junit_path_for_module(junit_directory: Path, module_path: str) -> Path:
    """Return one collision-free JUnit path for a repository test module."""

    filename = module_path.removesuffix(".py").replace("/", "__") + ".xml"
    return junit_directory / filename


def build_serial_test_command(
    *,
    module_path: str,
    junit_path: Path,
    base_temp: Path,
) -> tuple[str, ...]:
    """Build the isolated pytest command for one serial test module."""

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


def prepare_module_base_temp(*, project_root: Path, junit_path: Path) -> Path:
    """Create and return the parent-owned base-temp path for one module."""

    base_temp = project_root / ".pytest-tmp" / "serial" / junit_path.stem
    base_temp.parent.mkdir(parents=True, exist_ok=True)
    return base_temp


def run_serial_test_module(
    *,
    project_root: Path,
    module_path: str,
    junit_directory: Path,
) -> int:
    """Run one module in a fresh process and return its pytest exit code."""

    junit_path = junit_path_for_module(junit_directory, module_path)
    base_temp = prepare_module_base_temp(
        project_root=project_root,
        junit_path=junit_path,
    )
    command = build_serial_test_command(
        module_path=module_path,
        junit_path=junit_path,
        base_temp=base_temp,
    )
    completed = subprocess.run(  # noqa: S603
        command,
        cwd=project_root,
        check=False,
        timeout=_MODULE_TIMEOUT_SECONDS,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        _LOGGER.error("Pytest output for %s:\n%s", module_path, completed.stdout)
    return completed.returncode


def run_serial_test_modules(
    *,
    project_root: Path,
    junit_directory: Path,
    module_paths: Sequence[str] = tuple(sorted(SERIAL_TEST_MODULES)),
) -> tuple[str, ...]:
    """Run all serial modules independently and return the failing paths."""

    junit_directory.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    total = len(module_paths)
    for index, module_path in enumerate(module_paths, start=1):
        _LOGGER.info("Serial module %d/%d: %s", index, total, module_path)
        return_code = run_serial_test_module(
            project_root=project_root,
            module_path=module_path,
            junit_directory=junit_directory,
        )
        if return_code != 0:
            failures.append(module_path)
            _LOGGER.error(
                "Serial module failed with exit code %d: %s",
                return_code,
                module_path,
            )
    return tuple(failures)


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments and run the complete isolated serial partition."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--junit-dir",
        type=Path,
        required=True,
        help="Directory that receives one JUnit XML file per module.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    failures = run_serial_test_modules(
        project_root=Path.cwd(),
        junit_directory=args.junit_dir,
    )
    if failures:
        _LOGGER.error("%d serial test modules failed: %s", len(failures), failures)
        return 1
    _LOGGER.info("All %d serial test modules passed.", len(SERIAL_TEST_MODULES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

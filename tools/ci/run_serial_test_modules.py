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
from collections.abc import Sequence
from pathlib import Path
from tempfile import TemporaryDirectory

from tests.ci_test_policy import SERIAL_TEST_MODULES
from tools.ci.test_module_process import TestModuleRun, run_test_module


_LOGGER = logging.getLogger(__name__)


def run_serial_test_modules(
    *,
    project_root: Path,
    junit_directory: Path,
    module_paths: Sequence[str] = tuple(sorted(SERIAL_TEST_MODULES)),
) -> tuple[str, ...]:
    """Run all serial modules independently and return the failing paths."""

    junit_directory.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="sugarsubstitute-serial-") as temp_directory:
        base_temp_root = Path(temp_directory)
        failures: list[str] = []
        total = len(module_paths)
        for index, module_path in enumerate(module_paths, start=1):
            _LOGGER.info("Serial module %d/%d: %s", index, total, module_path)
            result = run_test_module(
                project_root=project_root,
                module_path=module_path,
                junit_directory=junit_directory,
                base_temp_root=base_temp_root,
            )
            if not result.passed:
                failures.append(module_path)
                _log_failure(result)
        return tuple(failures)


def _log_failure(result: TestModuleRun) -> None:
    """Log one complete failed fresh-process result."""

    _LOGGER.error("Pytest output for %s:\n%s", result.module_path, result.output)
    _LOGGER.error(
        "Serial module failed with exit code %d: %s",
        result.return_code,
        result.module_path,
    )


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

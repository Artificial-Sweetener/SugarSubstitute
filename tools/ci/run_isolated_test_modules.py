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

"""Run fresh-process test modules with bounded inter-module concurrency."""

from __future__ import annotations

import argparse
import logging
import os
from collections.abc import Sequence
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from tests.ci_test_policy import (
    ISOLATED_TEST_MODULES,
    isolated_test_worker_count,
)
from tools.ci.test_module_process import TestModuleRun, run_test_module
from tools.ci.test_partition_summary import write_test_partition_summary


_LOGGER = logging.getLogger(__name__)


def run_isolated_test_modules(
    *,
    project_root: Path,
    junit_directory: Path,
    module_paths: Sequence[str] = tuple(sorted(ISOLATED_TEST_MODULES)),
    available_workers: int | None = None,
) -> tuple[str, ...]:
    """Run each module in its own process and return every failing path."""

    junit_directory.mkdir(parents=True, exist_ok=True)
    worker_count = isolated_test_worker_count(
        os.cpu_count() if available_workers is None else available_workers
    )
    started_at = perf_counter()
    with TemporaryDirectory(prefix="sugarsubstitute-isolated-") as temp_directory:
        base_temp_root = Path(temp_directory)
        with ThreadPoolExecutor(
            max_workers=worker_count,
            thread_name_prefix="isolated-test-module",
        ) as executor:
            futures = {
                executor.submit(
                    run_test_module,
                    project_root=project_root,
                    module_path=module_path,
                    junit_directory=junit_directory,
                    base_temp_root=base_temp_root,
                ): module_path
                for module_path in module_paths
            }
            runs = _collect_results(futures, total=len(module_paths))
    write_test_partition_summary(
        junit_directory=junit_directory,
        lane="isolated",
        worker_count=worker_count,
        duration_seconds=perf_counter() - started_at,
        runs=runs,
    )
    return tuple(sorted(run.module_path for run in runs if not run.passed))


def _collect_results(
    futures: dict[Future[TestModuleRun], str],
    *,
    total: int,
) -> tuple[TestModuleRun, ...]:
    """Collect all terminal results while preserving actionable diagnostics."""

    runs: list[TestModuleRun] = []
    for index, future in enumerate(as_completed(futures), start=1):
        result = future.result()
        runs.append(result)
        _LOGGER.info(
            "Isolated module %d/%d completed: %s",
            index,
            total,
            result.module_path,
        )
        if result.passed:
            continue
        _LOGGER.error("Pytest output for %s:\n%s", result.module_path, result.output)
        _LOGGER.error(
            "Isolated module failed with exit code %d: %s",
            result.return_code,
            result.module_path,
        )
    return tuple(runs)


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments and run the complete fresh-process partition."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--junit-dir",
        type=Path,
        required=True,
        help="Directory that receives one JUnit XML file per module.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    failures = run_isolated_test_modules(
        project_root=Path.cwd(),
        junit_directory=args.junit_dir,
    )
    if failures:
        _LOGGER.error("%d isolated test modules failed: %s", len(failures), failures)
        return 1
    _LOGGER.info("All %d isolated test modules passed.", len(ISOLATED_TEST_MODULES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

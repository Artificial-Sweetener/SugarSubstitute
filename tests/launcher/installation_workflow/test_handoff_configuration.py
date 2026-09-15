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

"""Verify launcher handoff geometry, configuration recovery, and logging."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import logging
from pathlib import Path
import re
import subprocess
import sys

import pytest

from launcher.sugarsubstitute_launcher.config import (
    LauncherConfig,
    ReleaseSourceConfig,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.logging_setup import configure_launcher_logging
from sugarsubstitute_shared.windows_long_paths import logical_path
from launcher.sugarsubstitute_launcher.ui.window_geometry import (
    parse_handoff_geometry,
)


@pytest.mark.parametrize(
    "raw_geometry",
    [None, "", "1,2,3", "1,2,3,4,5", "left,2,300,200", "1,2,0,200"],
)
def test_handoff_geometry_rejects_missing_or_invalid_values(
    raw_geometry: str | None,
) -> None:
    """Leave default placement intact for invalid handoff geometry."""

    assert parse_handoff_geometry(raw_geometry) is None


def test_handoff_geometry_preserves_valid_window_frame() -> None:
    """Preserve position and dimensions from valid handoff geometry."""

    geometry = parse_handoff_geometry("-20,35,1260,800")

    assert geometry is not None
    assert (geometry.x(), geometry.y(), geometry.width(), geometry.height()) == (
        -20,
        35,
        1260,
        800,
    )


def test_launcher_config_upgrades_missing_release_source_to_github(
    tmp_path: Path,
) -> None:
    """Recover legacy schema-one configuration with GitHub update source."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    payload = LauncherConfig.from_layout(layout=layout).to_json()
    payload.pop("release_source")
    layout.config_path.parent.mkdir(parents=True, exist_ok=True)
    layout.config_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = LauncherConfig.load(layout.config_path)

    assert loaded.release_source == ReleaseSourceConfig.default()


def test_launcher_logging_writes_under_launcher_logs(tmp_path: Path) -> None:
    """Create launcher logs beneath launcher-owned state."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")

    log_path = configure_launcher_logging(layout=layout)

    assert log_path == layout.logs_dir / "launcher.log"
    assert log_path.parent.is_dir()


def test_launcher_logging_collapses_duplicate_handlers_for_the_same_file(
    tmp_path: Path,
) -> None:
    """Repeated or racing setup must never duplicate each diagnostic event."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    log_path = configure_launcher_logging(layout=layout)
    duplicate = logging.FileHandler(log_path, encoding="utf-8")
    root_logger = logging.getLogger()
    root_logger.addHandler(duplicate)
    try:
        configure_launcher_logging(layout=layout)
        matching = [
            handler
            for handler in root_logger.handlers
            if isinstance(handler, logging.FileHandler)
            and Path(logical_path(handler.baseFilename)).resolve() == log_path.resolve()
        ]

        assert len(matching) == 1
    finally:
        for handler in tuple(root_logger.handlers):
            if isinstance(handler, logging.FileHandler) and (
                Path(logical_path(handler.baseFilename)).resolve() == log_path.resolve()
            ):
                root_logger.removeHandler(handler)
                handler.close()


def test_launcher_logging_preserves_records_from_simultaneous_processes(
    tmp_path: Path,
) -> None:
    """A launch burst must never tear or combine diagnostic records."""

    install_root = tmp_path / "SugarSubstitute"
    worker_count = 2
    records_per_worker = 400
    worker_program = """
import logging
from pathlib import Path
import sys
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.logging_setup import configure_launcher_logging

layout = InstallLayout.from_root(Path(sys.argv[1]))
worker = int(sys.argv[2])
sys.stdout.write(f"ready:{worker}\\n")
sys.stdout.flush()
if sys.stdin.buffer.read(1) != b"x":
    raise RuntimeError("Logging writer release was not authenticated.")
configure_launcher_logging(layout=layout)
logger = logging.getLogger("qualification.concurrent_launcher_log")
for record in range(int(sys.argv[3])):
    logger.info("worker=%d record=%03d marker=%s", worker, record, "x" * 256)
logging.shutdown()
"""
    commands = [
        [
            sys.executable,
            "-c",
            worker_program,
            str(install_root),
            str(worker),
            str(records_per_worker),
        ]
        for worker in range(worker_count)
    ]

    def read_ready(process: subprocess.Popen[bytes]) -> bytes:
        """Read the writer's semantic barrier acknowledgement."""

        assert process.stdout is not None
        return bytes(process.stdout.readline())

    with (
        subprocess.Popen(  # noqa: S603
            commands[0],
            cwd=Path(__file__).resolve().parents[3],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            shell=False,
        ) as first,
        subprocess.Popen(  # noqa: S603
            commands[1],
            cwd=Path(__file__).resolve().parents[3],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            shell=False,
        ) as second,
    ):
        processes = (first, second)
        try:
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                ready = tuple(
                    executor.submit(read_ready, process) for process in processes
                )
                acknowledgements = tuple(
                    future.result(timeout=20.0) for future in ready
                )
            assert tuple(line.rstrip(b"\r\n") for line in acknowledgements) == (
                b"ready:0",
                b"ready:1",
            )
            for process in processes:
                assert process.stdin is not None
                process.stdin.write(b"x")
                process.stdin.close()
            return_codes = tuple(process.wait(timeout=20.0) for process in processes)
            assert return_codes == (0, 0)
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=5.0)

    log_path = InstallLayout.from_root(install_root).logs_dir / "launcher.log"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    record_pattern = re.compile(
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2} INFO process=\d+ "
        r"qualification\.concurrent_launcher_log worker=(\d+) record=(\d{3}) "
        r"marker=(x{256})$"
    )
    records = [record_pattern.fullmatch(line) for line in lines]

    assert len(lines) == worker_count * records_per_worker
    assert all(match is not None for match in records)
    assert {
        (int(match.group(1)), int(match.group(2)))
        for match in records
        if match is not None
    } == {
        (worker, record)
        for worker in range(worker_count)
        for record in range(records_per_worker)
    }

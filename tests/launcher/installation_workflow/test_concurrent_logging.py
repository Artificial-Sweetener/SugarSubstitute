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

"""Prove simultaneous runtime writers retain exact identities and complete records."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import subprocess
import sys

import psutil  # type: ignore[import-untyped]
import pytest

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.process_identity_evidence import (
    LAUNCHER_PROCESS_EVENT,
    LauncherProcessEvidence,
)
from sugarsubstitute_shared.process_identity import (
    ProcessIdentity,
    capture_process_identity,
)


@pytest.mark.parametrize("wrapped", [False, True])
def test_launcher_logging_preserves_records_from_simultaneous_processes(
    tmp_path: Path,
    wrapped: bool,
) -> None:
    """A launch burst must never tear or combine diagnostic records."""

    install_root = tmp_path / "SugarSubstitute"
    worker_count = 2
    records_per_worker = 400
    worker_program = """
import json
import logging
import os
from pathlib import Path
import sys
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.logging_setup import configure_launcher_logging

layout = InstallLayout.from_root(Path(sys.argv[1]))
worker = int(sys.argv[2])
sys.stdout.write(json.dumps({"worker": worker, "pid": os.getpid()}) + "\\n")
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

    if wrapped:
        # Windows venv Python can redirect through another native process. Exercise
        # that ownership boundary on every host without requiring Windows locally.
        wrapper_program = (
            "import subprocess, sys; raise SystemExit(subprocess.call(sys.argv[1:]))"
        )
        commands = [
            [sys.executable, "-c", wrapper_program, *command] for command in commands
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
        launch_identities = tuple(
            capture_process_identity(process.pid) for process in processes
        )
        executor = ThreadPoolExecutor(max_workers=worker_count)
        try:
            ready = tuple(executor.submit(read_ready, process) for process in processes)
            acknowledgements = tuple(future.result(timeout=20.0) for future in ready)
            expected_writers = tuple(
                _capture_held_writer(
                    acknowledgement, worker=index, launch=launch_identities[index]
                )
                for index, acknowledgement in enumerate(acknowledgements)
            )
            assert len({writer.identity for writer in expected_writers}) == worker_count
            with pytest.raises(AssertionError):
                _capture_held_writer(
                    acknowledgements[0], worker=0, launch=launch_identities[1]
                )
            reused_launch = ProcessIdentity(
                launch_identities[0].pid, launch_identities[0].created_at + 1.0
            )
            with pytest.raises(AssertionError):
                _capture_held_writer(
                    acknowledgements[0], worker=0, launch=reused_launch
                )
            if wrapped:
                assert all(
                    writer.identity != launch
                    for writer, launch in zip(expected_writers, launch_identities)
                )
            for process in processes:
                assert process.stdin is not None
                process.stdin.write(b"x")
                process.stdin.close()
            return_codes = tuple(process.wait(timeout=20.0) for process in processes)
            assert return_codes == (0, 0)
        finally:
            try:
                _stop_writers(processes)
            finally:
                executor.shutdown(wait=True, cancel_futures=True)

    log_path = InstallLayout.from_root(install_root).logs_dir / "launcher.log"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    identity_lines = [line for line in lines if LAUNCHER_PROCESS_EVENT in line]
    identity_records = [
        LauncherProcessEvidence.from_json(
            json.loads(line.split(LAUNCHER_PROCESS_EVENT, 1)[1])
        )
        for line in identity_lines
    ]
    record_pattern = re.compile(
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2} INFO process=(\d+) "
        r"qualification\.concurrent_launcher_log worker=(\d+) record=(\d{3}) "
        r"marker=(x{256})$"
    )
    records = [
        record_pattern.fullmatch(line)
        for line in lines
        if LAUNCHER_PROCESS_EVENT not in line
    ]

    assert len(lines) == worker_count * (records_per_worker + 1)
    assert len(identity_records) == worker_count
    assert set(identity_records) == set(expected_writers)
    assert all(match is not None for match in records)
    assert {
        (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        for match in records
        if match is not None
    } == {
        (expected_writers[worker].identity.pid, worker, record)
        for worker in range(worker_count)
        for record in range(records_per_worker)
    }


def _capture_held_writer(
    acknowledgement: bytes,
    *,
    worker: int,
    launch: ProcessIdentity,
) -> LauncherProcessEvidence:
    """Bind the barrier's runtime to the exact launched incarnation before release.

    The child reports its own PID over the inherited pipe. Observe its creation
    time, executable and live ancestry independently while it cannot yet log or
    exit. This supports direct Python and redirectors without accepting unrelated
    writers or merely allowing an arbitrary set of descendant-looking PIDs.
    """
    payload = json.loads(acknowledgement)
    assert isinstance(payload, dict) and payload.get("worker") == worker
    pid = payload.get("pid")
    assert isinstance(pid, int) and not isinstance(pid, bool) and pid > 0
    runtime = psutil.Process(pid)
    identity = ProcessIdentity(pid, float(runtime.create_time()))
    ancestor = runtime
    while True:
        observed = ProcessIdentity(ancestor.pid, float(ancestor.create_time()))
        if observed == launch:
            break
        assert observed.created_at >= launch.created_at
        ancestor = ancestor.parent()
        assert ancestor is not None
    parent = runtime.parent()
    assert parent is not None
    return LauncherProcessEvidence(
        identity=identity,
        parent_identity=ProcessIdentity(parent.pid, float(parent.create_time())),
        executable=str(runtime.exe()),
        parent_executable=str(parent.exe()),
    )


def _stop_writers(processes: tuple[subprocess.Popen[bytes], ...]) -> None:
    """Close all owned pipe writers before joining blocked barrier readers."""
    for process in processes:
        if process.poll() is None:
            try:
                children = psutil.Process(process.pid).children(recursive=True)
            except psutil.NoSuchProcess:
                children = []
            for child in reversed(children):
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    continue
            process.kill()
        process.wait(timeout=5.0)

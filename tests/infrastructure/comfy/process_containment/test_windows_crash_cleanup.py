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

"""Verify Windows Job Object cleanup when its owning process crashes."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import psutil  # type: ignore[import-untyped]  # psutil does not publish type metadata.
import pytest

pytestmark = pytest.mark.platforms("windows")


def test_windows_job_kills_live_child_when_owner_process_exits(
    tmp_path: Path,
) -> None:
    """Tear down a confirmed-live child when its Job Object owner exits abruptly."""

    helper_script_path = tmp_path / "job_owner_helper.py"
    child_pid_path = tmp_path / "child_pid.txt"
    ready_path = tmp_path / "ready.txt"
    helper_script_path.write_text(_windows_helper_script(), encoding="utf-8")

    helper_result = subprocess.run(
        [
            sys.executable,
            str(helper_script_path),
            str(child_pid_path),
            str(ready_path),
            str(tmp_path),
        ],
        cwd=str(_repo_root()),
        env=_helper_environment(),
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert helper_result.returncode == 0, helper_result.stderr
    assert child_pid_path.exists(), helper_result.stderr
    assert ready_path.exists(), helper_result.stderr
    child_pid = int(child_pid_path.read_text(encoding="utf-8").strip())
    assert int(ready_path.read_text(encoding="utf-8").strip()) == child_pid
    child_process = _open_process(child_pid)
    if child_process is None:
        return
    try:
        assert _wait_for_process_exit(child_process, timeout_seconds=10.0)
    finally:
        _ensure_process_exit(child_process)


def _open_process(pid: int) -> psutil.Process | None:
    """Return the observed child process unless the Job already removed it."""

    try:
        return psutil.Process(pid)
    except psutil.NoSuchProcess:
        return None


def _wait_for_process_exit(
    process: psutil.Process,
    *,
    timeout_seconds: float,
) -> bool:
    """Wait on semantic process state with a bounded native-failure timeout."""

    _gone, alive = psutil.wait_procs((process,), timeout=timeout_seconds)
    return not alive


def _ensure_process_exit(process: psutil.Process) -> None:
    """Prevent a containment regression from leaking the test child process."""

    if not process.is_running():
        return
    process.kill()
    try:
        process.wait(timeout=5.0)
    except psutil.NoSuchProcess:
        return


def _windows_helper_script() -> str:
    """Return the helper parent that proves child startup before crashing."""

    return """
import os
from pathlib import Path
import sys
import time

from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy.managed_process_containment import build_launch_request
from substitute.infrastructure.comfy.windows_job_containment import launch_in_job

child_pid_path = Path(sys.argv[1])
ready_path = Path(sys.argv[2])
workspace = Path(sys.argv[3])
child_command = (
    sys.executable,
    "-c",
    "from pathlib import Path; import os, sys, time; "
    "pid_path=Path(sys.argv[1]); "
    "pid_temp=pid_path.with_suffix('.tmp'); "
    "pid_temp.write_text(str(os.getpid()), encoding='utf-8'); "
    "pid_temp.replace(pid_path); "
    "time.sleep(300)",
    str(child_pid_path),
)
result = launch_in_job(
    endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
    workspace=workspace,
    request=build_launch_request(
        command=child_command,
        cwd=workspace,
        env=os.environ.copy(),
        capture_output=False,
    ),
)
startup_deadline = time.monotonic() + 10.0
published_child_pid = None
while published_child_pid is None and time.monotonic() < startup_deadline:
    try:
        published_child_pid = int(child_pid_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError):
        published_child_pid = None
    if published_child_pid is not None:
        break
    time.sleep(0.01)
if published_child_pid is None or published_child_pid <= 0:
    raise RuntimeError("Job-owned workload did not publish its process identity.")
ready_path.write_text(str(published_child_pid), encoding="utf-8")
os._exit(0)
""".strip()


def _helper_environment() -> dict[str, str]:
    """Return one helper-process environment with repository imports enabled."""

    environment = os.environ.copy()
    repo_root = str(_repo_root())
    existing_python_path = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = (
        repo_root
        if not existing_python_path
        else repo_root + os.pathsep + existing_python_path
    )
    return environment


def _repo_root() -> Path:
    """Return the repository root from the capability-owned test path."""

    return Path(__file__).resolve().parents[4]

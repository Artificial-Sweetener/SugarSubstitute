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

"""Integration tests for Windows Job Object crash-path cleanup."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from time import monotonic, sleep

import pytest

from substitute.infrastructure.comfy.managed_process_probe import is_process_running

pytestmark = pytest.mark.platforms("windows")


def test_windows_job_object_kills_child_when_owner_process_exits(
    tmp_path: Path,
) -> None:
    """Abrupt owner-process exit should tear down the entire Job Object child tree."""

    helper_script_path = tmp_path / "job_owner_helper.py"
    child_pid_path = tmp_path / "child_pid.txt"
    ready_path = tmp_path / "ready.txt"
    helper_script_path.write_text(_build_windows_helper_script(), encoding="utf-8")

    helper_result = subprocess.run(
        [
            sys.executable,
            str(helper_script_path),
            str(child_pid_path),
            str(ready_path),
            str(tmp_path),
        ],
        cwd=str(Path(__file__).resolve().parents[1]),
        env=_helper_environment(),
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert helper_result.returncode == 0, helper_result.stderr
    assert ready_path.exists(), helper_result.stderr
    child_pid = int(ready_path.read_text(encoding="utf-8").strip())
    assert _wait_for_process_exit(child_pid, timeout_seconds=10.0) is True


def _wait_for_process_exit(pid: int, *, timeout_seconds: float) -> bool:
    """Wait until the supplied pid no longer exists."""

    deadline = monotonic() + timeout_seconds
    while monotonic() < deadline:
        if not is_process_running(pid):
            return True
        sleep(0.1)
    return not is_process_running(pid)


def _build_windows_helper_script() -> str:
    """Return the helper parent script used to verify crash-path teardown."""

    return """
import os
from pathlib import Path
import sys

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
    "Path(sys.argv[1]).write_text(str(os.getpid()), encoding='utf-8'); "
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
ready_path.write_text(str(result.process.pid), encoding="utf-8")
os._exit(0)
""".strip()


def _helper_environment() -> dict[str, str]:
    """Return one helper-process environment with repo imports enabled."""

    environment = os.environ.copy()
    repo_root = str(Path(__file__).resolve().parents[1])
    existing_python_path = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = (
        repo_root
        if not existing_python_path
        else repo_root + os.pathsep + existing_python_path
    )
    return environment

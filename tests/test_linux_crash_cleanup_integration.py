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

"""Integration tests for Linux guardian crash-path cleanup."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic, sleep

import pytest

from substitute.infrastructure.comfy.posix_guardian_containment import (
    is_process_group_running,
)
from substitute.infrastructure.comfy.managed_process_probe import is_process_running

pytestmark = pytest.mark.platforms("linux")


def test_linux_guardian_kills_process_group_when_owner_process_exits(
    tmp_path: Path,
) -> None:
    """Abrupt owner-process exit should tear down the guardian-owned process group."""

    helper_script_path = tmp_path / "guardian_owner_helper.py"
    ready_path = tmp_path / "ready.json"
    helper_script_path.write_text(_build_linux_helper_script(), encoding="utf-8")

    helper_result = subprocess.run(
        [
            sys.executable,
            str(helper_script_path),
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
    payload = json.loads(ready_path.read_text(encoding="utf-8"))
    child_pid = int(payload["child_pid"])
    process_group_id = int(payload["process_group_id"])
    assert (
        _wait_for_linux_exit(child_pid, process_group_id, timeout_seconds=10.0) is True
    )


def _wait_for_linux_exit(
    child_pid: int,
    process_group_id: int,
    *,
    timeout_seconds: float,
) -> bool:
    """Wait until both the child pid and process group no longer exist."""

    deadline = monotonic() + timeout_seconds
    while monotonic() < deadline:
        if not is_process_running(child_pid) and not is_process_group_running(
            process_group_id
        ):
            return True
        sleep(0.1)
    return not is_process_running(child_pid) and not is_process_group_running(
        process_group_id
    )


def _build_linux_helper_script() -> str:
    """Return the helper parent script used to verify guardian crash cleanup."""

    return """
import json
import os
from pathlib import Path
import sys

from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy.posix_guardian_containment import launch_with_guardian
from substitute.infrastructure.comfy.managed_process_containment import build_launch_request

ready_path = Path(sys.argv[1])
workspace = Path(sys.argv[2])
result = launch_with_guardian(
    endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
    workspace=workspace,
    request=build_launch_request(
        command=(sys.executable, "-c", "import time; time.sleep(300)"),
        cwd=workspace,
        env=os.environ.copy(),
        capture_output=False,
    ),
)
ready_path.write_text(
    json.dumps(
        {
            "child_pid": result.metadata.pid,
            "process_group_id": result.metadata.process_group_id,
        }
    ),
    encoding="utf-8",
)
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

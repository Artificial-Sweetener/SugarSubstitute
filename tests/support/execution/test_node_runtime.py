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

"""Prove bounded real-Node execution and Windows cross-worker capacity."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess

import pytest

from tests.support.execution.node_runtime import (
    NodeProcessCapacityError,
    node_process_capacity,
    run_node,
)


def test_run_node_preserves_command_contract(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Pass exact arguments, paths, failure bounds, and checking policy to Node."""

    observed: dict[str, object] = {}

    def record_run(
        command: list[str],
        **options: object,
    ) -> subprocess.CompletedProcess[str]:
        """Capture one prepared Node subprocess call."""

        observed.update(command=command, options=options)
        return subprocess.CompletedProcess(command, 0, stdout="ready", stderr="")

    monkeypatch.setattr(subprocess, "run", record_run)

    completed = run_node(
        ("--eval", "process.stdout.write('ready')"),
        cwd=tmp_path,
        timeout_seconds=17.0,
        check=True,
    )

    assert completed.stdout == "ready"
    assert observed == {
        "command": ["node", "--eval", "process.stdout.write('ready')"],
        "options": {
            "cwd": tmp_path,
            "capture_output": True,
            "text": True,
            "timeout": 17.0,
            "check": True,
        },
    }


@pytest.mark.platforms("windows")
def test_windows_node_capacity_excludes_another_execution_thread() -> None:
    """Reject concurrent ownership and release capacity for the next caller."""

    def attempt_immediate_acquisition() -> bool:
        """Report whether a distinct thread can acquire the held named mutex."""

        try:
            with node_process_capacity(wait_milliseconds=0):
                return True
        except NodeProcessCapacityError:
            return False

    with ThreadPoolExecutor(max_workers=1) as executor:
        with node_process_capacity():
            assert (
                executor.submit(attempt_immediate_acquisition).result(timeout=5)
                is False
            )
        with node_process_capacity():
            pass

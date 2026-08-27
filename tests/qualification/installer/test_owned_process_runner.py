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

"""Qualify the bounded process-tree owner used by release verification."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from typing import cast

import pytest

from tools.ci import owned_process_runner
from tools.ci.owned_process_runner import run_owned_process


def test_owned_process_returns_complete_output_and_exit_status(tmp_path: Path) -> None:
    """The owner should preserve normal child output without shell mediation."""

    result = run_owned_process(
        [sys.executable, "-c", "print('owned-process-ready')"],
        cwd=tmp_path,
        timeout_seconds=10.0,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "owned-process-ready"
    assert result.stderr == ""


def test_owned_process_timeout_terminates_tree_and_preserves_diagnostics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A timed-out child must be reaped before its captured evidence is raised."""

    events: list[str] = []

    class _TimedOutProcess:
        """Model a child that exits only after tree termination."""

        pid = 4512
        returncode = -9

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            """Accept the production process-construction contract."""

        def communicate(self, timeout: float | None = None) -> tuple[str, str]:
            """Time out first, then return final bounded diagnostics."""

            if timeout is not None:
                events.append(f"wait:{timeout:g}")
                raise subprocess.TimeoutExpired("qualification", timeout)
            events.append("reap")
            return "last completed phase", "child stalled"

    monkeypatch.setattr(
        "tools.ci.owned_process_runner.subprocess.Popen",
        _TimedOutProcess,
    )
    monkeypatch.setattr(
        owned_process_runner,
        "terminate_owned_process_tree",
        lambda pid: events.append(f"terminate:{pid}"),
    )

    with pytest.raises(subprocess.TimeoutExpired) as captured:
        run_owned_process(
            ["qualification-child"],
            cwd=tmp_path,
            timeout_seconds=12.0,
        )

    error = captured.value
    assert cast(str, error.output) == "last completed phase"
    assert cast(str, error.stderr) == "child stalled"
    assert events == ["wait:12", "terminate:4512", "reap"]

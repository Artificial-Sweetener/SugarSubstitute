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

"""Verify application restarts remain inside the current supervisor."""

from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from substitute.app.bootstrap.startup_process_launch import (
    launch_command_working_directory,
    start_ready_app_process,
)
from sugarsubstitute_shared.crash_reporting.protocol import CleanExitOutcome


def test_launch_command_working_directory_uses_entrypoint_parent(
    tmp_path: Path,
) -> None:
    """Resolve the app entrypoint directory without starting a replacement."""

    entrypoint = tmp_path / "app" / "main.py"
    entrypoint.parent.mkdir()
    entrypoint.write_text("", encoding="utf-8")

    assert launch_command_working_directory([sys.executable, str(entrypoint)]) == (
        entrypoint.parent
    )
    assert launch_command_working_directory([sys.executable]) is None


def test_start_ready_app_process_requests_existing_supervisor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Authorize restart through IPC and mark the current crash run clean."""

    outcomes: list[CleanExitOutcome] = []
    monkeypatch.setattr(
        "substitute.app.bootstrap.application_instance_control.request_supervised_application_restart",
        lambda: True,
    )
    monkeypatch.setattr(
        "substitute.app.bootstrap.startup_process_launch.active_process_crash_runtime",
        lambda: SimpleNamespace(request_clean_exit=outcomes.append),
    )

    assert start_ready_app_process([sys.executable, str(tmp_path / "main.py")])
    assert outcomes == [CleanExitOutcome.RESTART]


def test_start_ready_app_process_fails_closed_without_supervisor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject restart when no authenticated long-lived launcher owns it."""

    monkeypatch.setattr(
        "substitute.app.bootstrap.application_instance_control.request_supervised_application_restart",
        lambda: False,
    )

    assert not start_ready_app_process([])
    assert not start_ready_app_process([sys.executable, "main.py"])

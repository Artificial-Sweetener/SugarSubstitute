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

"""Verify crash reports run only through the Qt-capable launcher process."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
import sys

import pytest

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.launcher_ui_process import (
    build_launcher_ui_command,
    run_crash_reporter,
    start_crash_reporter,
)
from launcher.sugarsubstitute_launcher.platforms import WINDOWS_X64


class _CompletedProcess:
    """Return one deterministic reporter process result."""

    def __init__(self, return_code: int) -> None:
        """Store the return code exposed by ``wait``."""

        self.return_code = return_code

    def wait(self, timeout: float | None = None) -> int:
        """Return the configured result without blocking."""

        assert timeout is None
        return self.return_code


class _ProcessStarter:
    """Capture launcher child commands without starting a process."""

    def __init__(self, return_code: int = 0) -> None:
        """Store the result returned by each captured child."""

        self.return_code = return_code
        self.calls: list[tuple[tuple[str, ...], Mapping[str, str] | None]] = []

    def __call__(
        self,
        command: Sequence[str],
        *,
        environment: Mapping[str, str] | None = None,
    ) -> tuple[_CompletedProcess, Path]:
        """Capture one exact command and return a completed fake process."""

        self.calls.append((tuple(command), environment))
        return _CompletedProcess(self.return_code), Path("reporter.log")


def test_frozen_installed_reporter_uses_qt_capable_ui_executable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The Qt-free installed supervisor must never present a report itself."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute", target=WINDOWS_X64)
    ui_executable = layout.launcher_support_path / "LauncherUi.exe"
    layout.launcher_support_path.mkdir(parents=True)
    ui_executable.write_bytes(b"launcher UI")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(layout.executable_path))
    monkeypatch.setattr(
        sys,
        "_MEIPASS",
        str(layout.launcher_support_path),
        raising=False,
    )

    command = build_launcher_ui_command(
        layout,
        (f"--install-root={layout.root}", "--show-crash-report=incident-1"),
    )

    assert command[0] == str(ui_executable)
    assert "--show-crash-report=incident-1" in command


def test_crash_reporter_start_and_recovery_share_one_command_owner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Immediate and missed reports must select the same child executable."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    starter = _ProcessStarter(return_code=7)
    monkeypatch.setattr(sys, "frozen", False, raising=False)

    start_crash_reporter(
        layout,
        "immediate",
        process_starter=starter,
    )
    result = run_crash_reporter(
        layout,
        "pending",
        locale_override="ja",
        process_starter=starter,
    )

    assert result == 7
    assert len(starter.calls) == 2
    immediate_command = starter.calls[0][0]
    pending_command = starter.calls[1][0]
    assert immediate_command[1:3] == ("-m", "launcher.sugarsubstitute_launcher")
    assert pending_command[:3] == immediate_command[:3]
    assert "--launcher-ui-child" in immediate_command
    assert "--launcher-ui-child" in pending_command
    assert "--show-crash-report=immediate" in immediate_command
    assert "--show-crash-report=pending" in pending_command
    assert "--locale=ja" in pending_command

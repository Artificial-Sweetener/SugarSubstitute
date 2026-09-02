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

"""Verify launcher QApplications inherit the production crash contract."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
import sys

import pytest

from launcher.sugarsubstitute_launcher.cli import parse_launcher_args
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.launcher_ui_supervision import (
    supervise_launcher_window,
)
from launcher.sugarsubstitute_launcher.platforms import WINDOWS_X64


class RecordingSupervisor:
    """Capture one child supervision request without creating a process."""

    def __init__(self, *, result: int = 0) -> None:
        """Store the terminal result returned to the parent launcher."""

        self.result = result
        self.calls: list[tuple[InstallLayout, tuple[str, ...], Mapping[str, str]]] = []

    def supervise(
        self,
        *,
        layout: InstallLayout,
        command: Sequence[str],
        environment: Mapping[str, str],
    ) -> int:
        """Record exact launch ownership and return the requested result."""

        self.calls.append((layout, tuple(command), environment))
        return self.result


def test_setup_window_relaunches_as_supervised_source_child(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Setup flags must cross the child boundary without shell reconstruction."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    arguments = parse_launcher_args(
        [
            "--continue-install",
            "--no-update-check",
            "--handoff-geometry=10,20,1200,800",
            "--manifest-url=https://example.invalid/manifest.json",
            "--locale=ja",
        ]
    )
    supervisor = RecordingSupervisor(result=7)
    monkeypatch.setattr(sys, "frozen", False, raising=False)

    result = supervise_launcher_window(
        layout=layout,
        arguments=arguments,
        repair=True,
        supervisor=supervisor,
    )

    assert result == 7
    assert len(supervisor.calls) == 1
    call_layout, command, _environment = supervisor.calls[0]
    assert call_layout == layout
    assert command[1:3] == ("-m", "launcher.sugarsubstitute_launcher")
    assert "--launcher-ui-child" in command
    assert f"--install-root={layout.root}" in command
    assert "--continue-install" in command
    assert "--repair" in command
    assert "--no-update-check" in command
    assert "--handoff-geometry=10,20,1200,800" in command
    assert "--manifest-url=https://example.invalid/manifest.json" in command
    assert "--locale=ja" in command


def test_frozen_standalone_setup_relaunches_its_single_executable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A downloaded one-file setup must not require an adjacent UI executable."""

    setup_executable = tmp_path / "downloads" / "renamed-installer.exe"
    layout = InstallLayout.from_root(
        tmp_path / "SugarSubstitute",
        target=WINDOWS_X64,
    )
    supervisor = RecordingSupervisor()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(setup_executable))
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "_MEI1234"), raising=False)

    supervise_launcher_window(
        layout=layout,
        arguments=parse_launcher_args([]),
        repair=False,
        supervisor=supervisor,
    )

    _call_layout, command, _environment = supervisor.calls[0]
    assert command[0] == str(setup_executable)
    assert "--launcher-ui-child" in command


def test_frozen_installed_launcher_uses_its_ui_executable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The installed supervisor must delegate Qt ownership to its UI executable."""

    layout = InstallLayout.from_root(
        tmp_path / "SugarSubstitute",
        target=WINDOWS_X64,
    )
    installed_launcher = layout.executable_path
    ui_executable = installed_launcher.with_name("LauncherUi.exe")
    layout.launcher_support_path.mkdir(parents=True)
    ui_executable.write_bytes(b"launcher UI")
    supervisor = RecordingSupervisor()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(installed_launcher))
    monkeypatch.setattr(
        sys,
        "_MEIPASS",
        str(layout.launcher_support_path),
        raising=False,
    )

    supervise_launcher_window(
        layout=layout,
        arguments=parse_launcher_args([]),
        repair=False,
        supervisor=supervisor,
    )

    _call_layout, command, _environment = supervisor.calls[0]
    assert command[0] == str(ui_executable)
    assert "--launcher-ui-child" in command

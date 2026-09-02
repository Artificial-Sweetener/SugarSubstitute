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

"""Verify first-run launcher installation and app-process handoff."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.first_run import FirstRunInstaller
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.process import (
    ProcessStartupError,
    build_app_launch_command,
    build_continue_install_command,
    start_detached,
)
from launcher.sugarsubstitute_launcher.release_sources import LocalFolderReleaseSource
from sugarsubstitute_shared.launcher_update.models import LauncherInstallationRecord
from sugarsubstitute_shared.subprocess_environment import (
    clean_frozen_parent_environment,
)
from sugarsubstitute_shared.windows_long_paths import subprocess_path
from tests.launcher.installation_workflow.first_run.support import (
    record_command,
    write_file,
    write_manifest,
    write_valid_launcher_bundle_zip,
    write_valid_payload_zip,
)


@pytest.mark.platforms("windows")
def test_first_run_installs_launcher_bundle_and_builds_continue_command(
    tmp_path: Path,
) -> None:
    """The permanent onedir launcher bundle is installed into the chosen root."""

    release_root = tmp_path / ".local-release-channel"
    app_zip = write_valid_payload_zip(release_root / "SugarSubstitute-app-v0.4.0.zip")
    launcher_zip = write_valid_launcher_bundle_zip(
        release_root / "SugarSubstitute-installer-payload-windows-x64-v0.4.0.zip"
    )
    write_manifest(
        release_root / "manifest.json", app_zip=app_zip, launcher_zip=launcher_zip
    )
    started_commands: list[list[str]] = []

    result = FirstRunInstaller(
        process_starter=record_command(started_commands)
    ).install_downloaded_launcher(
        install_root=tmp_path / "Programs" / "SugarSubstitute",
        release_source=LocalFolderReleaseSource(release_root),
    )

    assert result.layout.executable_path.read_bytes() == b"launcher"
    assert (result.layout.root / "Repair.exe").read_bytes() == b"repair launcher"
    assert (
        result.layout.root / "launcher-bin" / "python312.dll"
    ).read_bytes() == b"dll"
    assert result.continue_command == build_continue_install_command(
        layout=result.layout
    )
    assert started_commands == [result.continue_command]
    assert LauncherInstallationRecord.load(
        result.layout.launcher_installation_path
    ) == LauncherInstallationRecord(version="0.4.0", target_key="windows_x64")


def test_continue_install_command_carries_handoff_geometry(tmp_path: Path) -> None:
    """Continuation command should preserve the setup window frame."""

    layout = InstallLayout.from_root(tmp_path / "Programs" / "SugarSubstitute")

    command = build_continue_install_command(
        layout=layout, handoff_geometry="10,20,1260,800"
    )

    assert command == [
        subprocess_path(layout.executable_path),
        "--continue-install",
        f"--install-root={subprocess_path(layout.root)}",
        "--handoff-geometry=10,20,1260,800",
    ]


def test_app_launch_command_uses_hidden_console_python(tmp_path: Path) -> None:
    """The app handoff uses python.exe so startup failures can be logged."""

    layout = InstallLayout.from_root(tmp_path / "install")

    assert build_app_launch_command(layout=layout) == [
        subprocess_path(layout.runtime_python),
        subprocess_path(layout.app_entrypoint),
        f"--install-root={subprocess_path(layout.root)}",
    ]


def test_start_detached_reports_immediate_app_startup_exit(tmp_path: Path) -> None:
    """Immediate app-process exit is reported with startup log context."""

    layout = InstallLayout.from_root(tmp_path / "install")
    write_file(layout.app_entrypoint, "raise RuntimeError('boom')\n")

    with pytest.raises(ProcessStartupError, match="exited before the setup window"):
        start_detached(
            ["python", str(layout.app_entrypoint), f"--install-root={layout.root}"]
        )

    startup_log = layout.logs_dir / "app-startup.log"
    assert startup_log.is_file()
    assert "RuntimeError: boom" in startup_log.read_text(encoding="utf-8")


def test_start_detached_uses_install_logs_for_setup_child(tmp_path: Path) -> None:
    """A setup child writes diagnostics outside its read-only launch location."""

    layout = InstallLayout.from_root(tmp_path / "install")
    setup_child = tmp_path / "mounted-image" / "setup_child.py"
    write_file(setup_child, "raise RuntimeError('setup boom')\n")

    with pytest.raises(ProcessStartupError, match="exited before the setup window"):
        start_detached(
            [sys.executable, str(setup_child), f"--install-root={layout.root}"]
        )

    startup_log = layout.logs_dir / "app-startup.log"
    assert startup_log.is_file()
    assert "RuntimeError: setup boom" in startup_log.read_text(encoding="utf-8")


def test_child_process_environment_removes_pyinstaller_runtime_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Child app launches must not inherit PyInstaller or bundled Qt state."""

    meipass = tmp_path / "_MEI12345"
    bundled_bin = meipass / "PySide6"
    normal_bin = tmp_path / "normal-bin"
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    parent_environment = {
        "PATH": f"{bundled_bin}{os.pathsep}{normal_bin}",
        "LD_LIBRARY_PATH": f"{bundled_bin}{os.pathsep}{normal_bin}",
        "LD_LIBRARY_PATH_ORIG": str(normal_bin),
        "DYLD_LIBRARY_PATH": str(bundled_bin),
        "QT_PLUGIN_PATH": str(meipass / "PySide6" / "Qt" / "plugins"),
        "_PYI_APPLICATION_HOME_DIR": str(meipass),
        "HANDOFF": "private",
    }

    environment = clean_frozen_parent_environment(parent_environment)

    path_entries = environment["PATH"].split(os.pathsep)
    assert str(bundled_bin) not in path_entries
    assert str(normal_bin) in path_entries
    assert environment["LD_LIBRARY_PATH"] == str(normal_bin)
    assert "LD_LIBRARY_PATH_ORIG" not in environment
    assert "DYLD_LIBRARY_PATH" not in environment
    assert "QT_PLUGIN_PATH" not in environment
    assert "_PYI_APPLICATION_HOME_DIR" not in environment
    assert environment["HANDOFF"] == "private"
    assert str(bundled_bin) in parent_environment["PATH"]

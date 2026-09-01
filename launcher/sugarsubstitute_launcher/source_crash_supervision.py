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

"""Relaunch direct source execution beneath the normal crash supervisor."""

from __future__ import annotations

from collections.abc import Sequence
import os
from pathlib import Path
import subprocess
import sys

from launcher.sugarsubstitute_launcher.crash_supervisor import (
    ApplicationCrashSupervisor,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.windows_long_paths import subprocess_path


def supervise_source_application(*, argv: Sequence[str], app_root: Path) -> int:
    """Run one source app child beneath the production crash contract."""

    layout = InstallLayout.from_root(app_root)
    supervisor = ApplicationCrashSupervisor(
        reporter_starter=_start_source_crash_reporter,
        native_runtime_resolver=lambda _layout: _source_native_runtime(layout),
    )
    return supervisor.supervise(
        layout=layout,
        command=[
            subprocess_path(Path(sys.executable)),
            subprocess_path(app_root / "main.py"),
            *argv[1:],
        ],
        environment=os.environ,
    )


def _source_native_runtime(layout: InstallLayout) -> tuple[Path, Path]:
    """Return platform Crashpad assets built into the source checkout."""

    target_directory = (
        layout.root
        / "third_party"
        / "bin"
        / "crashpad"
        / layout.target.key.replace("_", "-")
    )
    return (
        target_directory / layout.crashpad_handler_path.name,
        target_directory / layout.crashpad_client_library_path.name,
    )


def _start_source_crash_reporter(layout: InstallLayout, incident_id: str) -> None:
    """Start the independent reporter through the source launcher module."""

    subprocess.Popen(  # noqa: S603
        [
            subprocess_path(Path(sys.executable)),
            "-m",
            "launcher.sugarsubstitute_launcher",
            f"--install-root={subprocess_path(layout.root)}",
            f"--show-crash-report={incident_id}",
        ],
        cwd=layout.root,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        shell=False,
    )


__all__ = ["supervise_source_application"]

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

"""Start the detached app-runtime helper that can replace the launcher."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from sugarsubstitute_shared.launcher_update.models import LauncherUpdateRequest


def schedule_launcher_update(
    *,
    request_path: Path,
    runtime_python: Path,
    app_dir: Path,
    relaunch: bool,
    wait_pid: int | None,
) -> int:
    """Persist process behavior and start the detached replacement helper."""

    request = LauncherUpdateRequest.load(request_path).with_process_behavior(
        relaunch=relaunch,
        wait_pid=wait_pid,
    )
    request.save(request_path)
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(app_dir)
    log_path = request.install_root / "launcher" / "logs" / "launcher-update.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    creationflags = 0
    startupinfo = None
    if sys.platform == "win32":
        creationflags = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    with log_path.open("a", encoding="utf-8") as output:
        process = subprocess.Popen(  # noqa: S603
            [
                str(runtime_python),
                "-m",
                "sugarsubstitute_shared.launcher_update.helper",
                str(request_path),
            ],
            cwd=request.install_root,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.STDOUT,
            close_fds=True,
            creationflags=creationflags,
            startupinfo=startupinfo,
            shell=False,
        )
    return process.pid


__all__ = ["schedule_launcher_update"]

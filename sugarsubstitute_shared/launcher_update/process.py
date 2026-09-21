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

"""Start a durable detached helper that can update launcher generations."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import os

from sugarsubstitute_shared.launcher_update.request import LauncherUpdateRequest
from sugarsubstitute_shared.launcher_update.delegation_contract import (
    supports_launcher_delegation,
)
from sugarsubstitute_shared.launcher_update.targets import (
    launcher_bundle_target_for_key,
)
from sugarsubstitute_shared.crash_reporting.protocol import (
    without_crash_supervision_environment,
)
from sugarsubstitute_shared.application_readiness import (
    without_application_readiness_environment,
)
from sugarsubstitute_shared.subprocess_environment import (
    clean_frozen_parent_environment,
    standard_child_process_dll_search_path,
)
from sugarsubstitute_shared.windows_long_paths import (
    operational_path,
    subprocess_path,
    subprocess_working_directory,
)


def schedule_launcher_update(
    *,
    request_path: Path,
    runtime_python: Path,
    app_dir: Path,
    relaunch: bool,
    wait_pid: int | None,
) -> int:
    """Persist process behavior and start the durable replacement helper.

    A permanent delegating baseline owns all current-protocol mutations. Only a
    pre-bootstrap installation uses the application-runtime helper for its
    one-time migration into that durable ownership model.
    """

    from sugarsubstitute_shared.process_identity import capture_process_identity

    request_path = operational_path(request_path)
    runtime_python = operational_path(runtime_python)
    app_dir = operational_path(app_dir)
    request = LauncherUpdateRequest.load(request_path).with_process_behavior(
        relaunch=relaunch,
        wait_identity=capture_process_identity(wait_pid)
        if wait_pid is not None
        else None,
    )
    request.save(request_path)
    environment = without_application_readiness_environment(
        without_crash_supervision_environment(clean_frozen_parent_environment())
    )
    install_root = operational_path(request.install_root)
    target = launcher_bundle_target_for_key(request.target_key)
    if supports_launcher_delegation(install_root, target):
        command = [
            subprocess_path(install_root / target.executable_relative_path),
            "--apply-launcher-update",
            subprocess_path(request_path),
        ]
    else:
        environment["PYTHONPATH"] = subprocess_path(app_dir)
        command = [
            subprocess_path(runtime_python),
            "-m",
            "sugarsubstitute_shared.launcher_update.helper",
            subprocess_path(request_path),
        ]
    log_path = install_root / "launcher" / "logs" / "launcher-update.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as output:
        return _start_independent(
            command,
            cwd=install_root,
            environment=environment,
            output_fd=output.fileno(),
        )


def relaunch_updated_launcher(executable_path: Path) -> None:
    """Start the newly promoted launcher without inheriting helper handles."""

    with open(os.devnull, "wb") as output:
        _start_independent(
            [subprocess_path(executable_path)],
            cwd=executable_path.parent,
            environment=without_application_readiness_environment(
                without_crash_supervision_environment(clean_frozen_parent_environment())
            ),
            output_fd=output.fileno(),
        )


def _start_independent(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    output_fd: int,
) -> int:
    """Require independent native lifetime before committing either update handoff."""
    with standard_child_process_dll_search_path():
        if sys.platform == "win32":
            from sugarsubstitute_shared.windows_independent_process import (
                start_independent_windows_process,
            )

            return start_independent_windows_process(
                command,
                environment=environment,
                cwd=cwd,
                output_fd=output_fd,
            )
        process = subprocess.Popen(
            command,
            cwd=subprocess_working_directory(cwd),
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=output_fd,
            stderr=subprocess.STDOUT,
            close_fds=True,
            start_new_session=True,
            shell=False,
        )
        return process.pid


__all__ = ["schedule_launcher_update", "relaunch_updated_launcher"]

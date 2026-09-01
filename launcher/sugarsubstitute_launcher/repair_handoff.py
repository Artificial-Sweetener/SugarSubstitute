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

"""Stage and launch an independent repair helper outside replaceable roots."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import os
from pathlib import Path
import secrets
import shutil

from launcher.sugarsubstitute_launcher.application.repair.request import (
    PreparedRepairRequest,
)
from launcher.sugarsubstitute_launcher.process import start_detached_handoff
from launcher.sugarsubstitute_launcher.repair_process import capture_process_identity
from sugarsubstitute_shared.launcher_update.targets import (
    launcher_bundle_target_for_key,
)
from sugarsubstitute_shared.windows_long_paths import subprocess_path


class RepairHandoffError(RuntimeError):
    """Report an independent helper that cannot be staged or launched safely."""


ProcessStarter = Callable[[Sequence[str]], None]


def launch_prepared_repair_helper(
    *,
    request_path: Path,
    starter: ProcessStarter = start_detached_handoff,
    current_pid: int | None = None,
) -> Path:
    """Copy the verified helper, bind the caller identity, and start it hidden."""

    request = PreparedRepairRequest.load(request_path)
    target = launcher_bundle_target_for_key(request.target_key)
    source = request.staged_launcher_dir / target.executable_relative_path
    adjacent_repair = request.staged_launcher_dir / "Repair.exe"
    if adjacent_repair.is_file():
        source = adjacent_repair
    if not source.is_file():
        raise RepairHandoffError(f"Prepared repair helper is missing: {source}")
    helper_dir = request.install_root / ".repair" / "helper" / request.version
    helper_dir.mkdir(parents=True, exist_ok=True)
    helper = helper_dir / source.name
    temporary = helper.with_name(f".{helper.name}.{secrets.token_hex(4)}.tmp")
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, helper)
    finally:
        temporary.unlink(missing_ok=True)
    identity = capture_process_identity(current_pid or os.getpid())
    request.with_process_behavior(
        wait_pid=identity.pid,
        wait_process_created_at=identity.created_at,
        relaunch=request.relaunch,
    ).save(request_path)
    starter(
        (
            subprocess_path(helper),
            f"--execute-repair-request={subprocess_path(request_path)}",
        )
    )
    return helper


__all__ = ["RepairHandoffError", "launch_prepared_repair_helper"]

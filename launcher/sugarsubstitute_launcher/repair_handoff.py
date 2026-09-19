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

from collections.abc import Mapping, Sequence
import os
from pathlib import Path
from typing import Protocol

from launcher.sugarsubstitute_launcher.application.repair.request import (
    PreparedRepairRequest,
    PreparedRepairRequestError,
)
from launcher.sugarsubstitute_launcher.process_execution import start_detached_handoff
from sugarsubstitute_shared.process_identity import capture_process_identity
from sugarsubstitute_shared.launcher_update.targets import (
    launcher_bundle_target_for_key,
)
from sugarsubstitute_shared.windows_long_paths import subprocess_path


class ProcessStarter(Protocol):
    """Launch a repair child with the exact outgoing ownership envelope."""

    def __call__(
        self, command: Sequence[str], *, environment: Mapping[str, str]
    ) -> None:
        """Start an independent process with explicit inherited context."""


def launch_prepared_repair_helper(
    *,
    request_path: Path,
    starter: ProcessStarter = start_detached_handoff,
    current_pid: int | None = None,
) -> Path:
    """Retain an independent launcher bundle and bind its outgoing caller identity."""

    request = PreparedRepairRequest.load(request_path)
    if request.helper_bundle_dir is None:
        raise PreparedRepairRequestError(
            "Repair has no prepared independent launcher bundle."
        )
    target = launcher_bundle_target_for_key(request.target_key)
    helper = request.helper_bundle_dir / target.executable_relative_path
    if not helper.is_file():
        raise PreparedRepairRequestError("Prepared repair helper is missing.")
    identity = capture_process_identity(current_pid or os.getpid())
    request.with_process_behavior(
        wait_pid=identity.pid,
        wait_process_created_at=identity.created_at,
        relaunch=request.relaunch,
    ).save(request_path)
    from sugarsubstitute_shared.qt_application_instance_control import (
        active_application_supervisor_identity,
    )
    from sugarsubstitute_shared.supervisor_handoff import with_supervisor_handoff

    environment = dict(os.environ)
    supervisor = active_application_supervisor_identity()
    if supervisor is not None:
        environment = with_supervisor_handoff(environment, supervisor)
    starter(
        (
            subprocess_path(helper),
            f"--execute-repair-request={subprocess_path(request_path)}",
        ),
        environment=environment,
    )
    return helper


__all__ = ["launch_prepared_repair_helper"]

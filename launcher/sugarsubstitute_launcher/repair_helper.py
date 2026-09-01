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

"""Run a prepared repair after its invoking launcher has exited."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from launcher.sugarsubstitute_launcher.application.repair.execution_service import (
    CompletedRepair,
    RepairExecutionService,
)
from launcher.sugarsubstitute_launcher.application.repair.request import (
    PreparedRepairRequest,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.platforms import launcher_target_for_key
from launcher.sugarsubstitute_launcher.process import (
    build_app_launch_command,
    start_detached,
)
from launcher.sugarsubstitute_launcher.repair_process import (
    RepairProcessIdentity,
    wait_for_process_exit,
)


class RepairHelperError(RuntimeError):
    """Report an invalid helper request or incomplete repair handoff."""


RepairExecutor = Callable[[PreparedRepairRequest], CompletedRepair]
ProcessWaiter = Callable[[RepairProcessIdentity], None]
AppStarter = Callable[[tuple[str, ...]], None]


def run_prepared_repair(
    request_path: Path,
    *,
    executor: RepairExecutor | None = None,
    process_waiter: ProcessWaiter = wait_for_process_exit,
    app_starter: AppStarter | None = None,
) -> CompletedRepair:
    """Wait for the exact caller, execute the repair, and optionally relaunch."""

    request = PreparedRepairRequest.load(request_path)
    expected_path = request.install_root / ".repair" / "prepared.json"
    if request_path.resolve() != expected_path.resolve():
        raise RepairHelperError(
            f"Repair request is outside its authoritative path: {request_path}"
        )
    if request.wait_pid is not None:
        assert request.wait_process_created_at is not None
        process_waiter(
            RepairProcessIdentity(
                pid=request.wait_pid,
                created_at=request.wait_process_created_at,
            )
        )
    execute = executor or RepairExecutionService().execute_application
    result = execute(request)
    request_path.unlink(missing_ok=True)
    if request.relaunch:
        target = launcher_target_for_key(request.target_key)
        layout = InstallLayout.from_root(request.install_root, target=target)
        command = tuple(build_app_launch_command(layout=layout))
        (app_starter or _start_app)(command)
    return result


def _start_app(command: tuple[str, ...]) -> None:
    """Start the repaired application with normal hidden handoff behavior."""

    start_detached(command)


__all__ = ["RepairHelperError", "run_prepared_repair"]

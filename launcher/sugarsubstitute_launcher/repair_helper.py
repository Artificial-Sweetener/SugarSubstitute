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

"""Own recovery, execution, and retirement of one prepared repair without Qt."""

from __future__ import annotations

from sugarsubstitute_shared.installation_mutation import (
    InstallationMutationOwnership,
    installation_mutation,
)

from typing import Protocol
from pathlib import Path
from collections.abc import Callable

from launcher.sugarsubstitute_launcher.installation_recovery import InstallationRecovery
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.application.repair.progress import (
    RepairProgressObserver,
)

from launcher.sugarsubstitute_launcher.application.repair.execution_result import (
    CompletedRepair,
)
from launcher.sugarsubstitute_launcher.application.repair.request import (
    PreparedRepairRequest,
)
from launcher.sugarsubstitute_launcher.application.repair.composition import (
    build_repair_execution_service,
)
from launcher.sugarsubstitute_launcher.platforms import launcher_target_for_key


class RepairHelperError(RuntimeError):
    """Report an invalid helper request or incomplete repair handoff."""


class RepairExecutor(Protocol):
    """Execute one request within the explicitly retained installation operation."""

    def __call__(
        self, request: PreparedRepairRequest, *, mutation: InstallationMutationOwnership
    ) -> CompletedRepair:
        """Return the outcome without establishing a competing operation."""
        ...


def run_prepared_repair(
    request_path: Path,
    *,
    executor: RepairExecutor | None = None,
    ownership: InstallationMutationOwnership | None = None,
    progress_observer: RepairProgressObserver | None = None,
    output_callback: Callable[[str], None] | None = None,
) -> CompletedRepair:
    """Recover before constructing adapters and retire intent only after commit.

    Keep installation authority in this execution boundary so presentation can
    supervise or replace the execution process without implementing repair rules.
    """

    request = load_prepared_repair_request(request_path)
    with installation_mutation(request.install_root, ownership=ownership) as operation:
        target = launcher_target_for_key(request.target_key)
        InstallationRecovery(
            InstallLayout.from_root(request.install_root, target=target)
        ).recover(ownership=operation)
        execute = (
            executor
            or build_repair_execution_service(
                target=target,
                progress_observer=progress_observer,
                output_callback=output_callback,
            ).execute_application
        )
        result = execute(request, mutation=operation)
        request_path.unlink(missing_ok=True)
        return result


def load_prepared_repair_request(request_path: Path) -> PreparedRepairRequest:
    """Require the installation's authoritative handoff path before accepting work."""
    request = PreparedRepairRequest.load(request_path)
    expected_path = request.request_path
    if request_path.resolve() != expected_path.resolve():
        raise RepairHelperError(
            f"Repair request is outside its authoritative path: {request_path}"
        )
    return request


__all__ = ["RepairHelperError", "run_prepared_repair", "load_prepared_repair_request"]

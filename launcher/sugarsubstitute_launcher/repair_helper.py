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

"""Execute and retire one authoritative request beneath its lifecycle owner."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

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


RepairExecutor = Callable[[PreparedRepairRequest], CompletedRepair]


def run_prepared_repair(
    request_path: Path,
    *,
    executor: RepairExecutor | None = None,
) -> CompletedRepair:
    """Execute under established ownership and retire the request only after success."""

    request = load_prepared_repair_request(request_path)
    execute = (
        executor
        or build_repair_execution_service(
            target=launcher_target_for_key(request.target_key)
        ).execute_application
    )
    result = execute(request)
    request_path.unlink(missing_ok=True)
    return result


def load_prepared_repair_request(request_path: Path) -> PreparedRepairRequest:
    """Require the installation's authoritative handoff path before accepting work."""
    request = PreparedRepairRequest.load(request_path)
    expected_path = request.install_root / ".repair" / "prepared.json"
    if request_path.resolve() != expected_path.resolve():
        raise RepairHelperError(
            f"Repair request is outside its authoritative path: {request_path}"
        )
    return request


__all__ = ["RepairHelperError", "run_prepared_repair", "load_prepared_repair_request"]

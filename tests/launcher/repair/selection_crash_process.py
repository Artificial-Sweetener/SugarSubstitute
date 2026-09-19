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

"""Interrupt a test-owned repair process after durable selection promotion."""

from __future__ import annotations

import os
from pathlib import Path
import sys

from launcher.sugarsubstitute_launcher.application.repair.execution_service import (
    RepairExecutionService,
)
from launcher.sugarsubstitute_launcher.application.repair.request import (
    PreparedRepairRequest,
)
from launcher.sugarsubstitute_launcher.repair_transaction import RepairTransaction
from sugarsubstitute_shared.launcher_update.bundle_paths import LauncherBundlePaths
from .execution_support import _RuntimeProvisioner


def main() -> int:
    """Exit without Python cleanup at the caller's fixture-owned journal boundary."""
    request = PreparedRepairRequest.load(Path(sys.argv[1]))
    selection = LauncherBundlePaths(request.install_root).selection

    def interrupt_after_selection(_source: Path, destination: Path) -> None:
        """Model process death after the new selection has reached the filesystem."""
        if destination.resolve() == selection.resolve():
            os._exit(73)

    RepairExecutionService(
        runtime_provisioner=_RuntimeProvisioner(),
        transaction=RepairTransaction(after_move=interrupt_after_selection),
    ).execute_application(request)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

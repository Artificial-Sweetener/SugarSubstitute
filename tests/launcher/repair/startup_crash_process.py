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

"""Interrupt a repair at a caller-selected startup dependency boundary."""

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
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.platforms import launcher_target_for_key
from launcher.sugarsubstitute_launcher.repair_transaction import RepairTransaction
from .execution_support import _RuntimeProvisioner


def main() -> int:
    """Exit after quarantine has removed a startup dependency from the installation."""
    request = PreparedRepairRequest.load(Path(sys.argv[1]))
    layout = InstallLayout.from_root(
        request.install_root, target=launcher_target_for_key(request.target_key)
    )
    boundary = layout.config_path if sys.argv[2] == "config" else layout.app_dir

    def interrupt(source: Path, _destination: Path) -> None:
        """Terminate only this fixture process at the persisted move boundary."""
        if source.resolve() == boundary.resolve():
            os._exit(73)

    RepairExecutionService(
        runtime_provisioner=_RuntimeProvisioner(),
        transaction=RepairTransaction(after_move=interrupt),
    ).execute_application(request)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

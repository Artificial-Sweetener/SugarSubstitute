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

"""Exercise payload activation in a hidden fixture-owned native process."""

from __future__ import annotations
import os
from pathlib import Path
import sys
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.update_activation import PendingUpdateActivation
from launcher.sugarsubstitute_launcher.update_state import LauncherUpdateState
from sugarsubstitute_shared.installation_mutation import InstallationMutationBusyError


def main() -> int:
    """Report contention or terminate after moving the fixture runtime."""
    layout = InstallLayout.from_root(Path(sys.argv[1]))
    try:
        activation = PendingUpdateActivation.begin(
            layout=layout,
            successful_state=LauncherUpdateState(installed_app_version="2.0.0"),
        )
        activation.prepare_runtime()
        os._exit(73)
    except InstallationMutationBusyError:
        return 17


if __name__ == "__main__":
    raise SystemExit(main())

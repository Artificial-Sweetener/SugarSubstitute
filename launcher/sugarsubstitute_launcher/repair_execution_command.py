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

"""Build repair execution commands from the verified independent bundle."""

from collections.abc import Sequence
from launcher.sugarsubstitute_launcher.application.repair.request import (
    PreparedRepairRequest,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.launcher_ui_process import (
    build_launcher_ui_command,
)
from launcher.sugarsubstitute_launcher.platforms import launcher_target_for_key
from sugarsubstitute_shared.windows_long_paths import subprocess_path


def build_repair_execution_command(request: PreparedRepairRequest) -> Sequence[str]:
    """Use the retained bundle so mutation cannot replace the executing runtime."""
    if request.helper_bundle_dir is None:
        raise ValueError("Repair execution requires an independent launcher bundle.")
    bundle = InstallLayout.from_root(
        request.helper_bundle_dir, target=launcher_target_for_key(request.target_key)
    )
    return build_launcher_ui_command(
        bundle, (f"--repair-worker-request={subprocess_path(request.request_path)}",)
    )

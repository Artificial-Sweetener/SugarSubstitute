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

"""Admit completed preparation only within the parent's selected repair boundary."""

from launcher.sugarsubstitute_launcher.application.repair.models import RepairScope
from launcher.sugarsubstitute_launcher.application.repair.paths import (
    RepairPreparationPaths,
)
from launcher.sugarsubstitute_launcher.application.repair.preparation_service import (
    RepairPreparation,
)
from launcher.sugarsubstitute_launcher.application.repair.request import (
    PreparedRepairRequest,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.windows_long_paths import operational_path


def load_preparation_result(
    message: dict[str, object], *, layout: InstallLayout, scope: RepairScope
) -> RepairPreparation:
    """Derive the sole allowed request path and verify intent before repair handoff."""
    version, preparation_id = message.get("version"), message.get("preparation_id")
    if (
        set(message) != {"kind", "version", "preparation_id"}
        or message.get("kind") != "succeeded"
        or not isinstance(version, str)
        or not isinstance(preparation_id, str)
    ):
        raise ValueError("Repair preparation outcome is malformed.")
    root = operational_path(layout.root).resolve()
    paths = RepairPreparationPaths(root, version, preparation_id)
    request = PreparedRepairRequest.load(paths.request_path)
    if (
        operational_path(request.install_root).resolve() != root
        or request.target_key != layout.target.key
        or request.scope != scope
        or request.version != version
        or request.preparation_id != preparation_id
        or request.helper_bundle_dir is None
        or request.wait_pid is not None
        or request.wait_process_created_at is not None
        or request.relaunch
    ):
        raise ValueError("Repair worker result differs from the selected preparation.")
    return RepairPreparation(request=request, request_path=paths.request_path)

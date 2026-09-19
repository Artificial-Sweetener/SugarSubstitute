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

"""Stage an independently runnable repair bundle outside replacement destinations."""

from __future__ import annotations

import logging
from pathlib import Path
import shutil

from launcher.sugarsubstitute_launcher.application.repair.integrity import (
    verify_directory_tree_sha256,
)
from launcher.sugarsubstitute_launcher.application.repair.request import (
    PreparedRepairRequest,
)
from sugarsubstitute_shared.launcher_update.bundle_validation import (
    validate_launcher_bundle,
)
from sugarsubstitute_shared.launcher_update.targets import (
    launcher_bundle_target_for_key,
)
from launcher.sugarsubstitute_launcher.repair_artifact_storage import (
    create_repair_artifact_directory,
    REPAIR_SESSION_PREFIX,
)

_LOGGER = logging.getLogger(__name__)


def stage_independent_repair_bundle(request: PreparedRepairRequest) -> Path:
    """Verify and copy the complete platform bundle before launching any of it."""
    target = launcher_bundle_target_for_key(request.target_key)
    source = request.staged_launcher_dir
    verify_directory_tree_sha256(source, expected=request.staged_launcher_sha256)
    validate_launcher_bundle(bundle_dir=source, target=target)
    parent = request.install_root / ".repair" / "helper" / request.version
    retained = create_repair_artifact_directory(
        install_root=request.install_root,
        parent=parent,
        prefix=REPAIR_SESSION_PREFIX,
    )
    bundle = retained / "bundle"
    try:
        shutil.copytree(source, bundle, symlinks=True)
        verify_directory_tree_sha256(bundle, expected=request.staged_launcher_sha256)
        validate_launcher_bundle(bundle_dir=bundle, target=target)
    except (OSError, RuntimeError):
        _LOGGER.exception(
            "Could not prepare the independent repair bundle",
            extra={"operation": "repair_handoff", "retained_path": str(retained)},
        )
        raise
    _LOGGER.info(
        "Prepared independently runnable repair bundle",
        extra={
            "operation": "repair_handoff",
            "bundle_path": str(bundle),
            "target": target.key,
        },
    )
    return bundle

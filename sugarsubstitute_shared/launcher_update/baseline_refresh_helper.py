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

"""Replace an incompatible root from its independently running selected launcher."""

from __future__ import annotations

from pathlib import Path

from sugarsubstitute_shared.installation_mutation import installation_mutation
from sugarsubstitute_shared.launcher_update.attempt_status import (
    LauncherUpdateAttemptPhase,
    LauncherUpdateAttemptStatus,
    LauncherUpdateAttemptStore,
)
from sugarsubstitute_shared.launcher_update.baseline_transaction import (
    LauncherBaselineTransaction,
)
from sugarsubstitute_shared.launcher_update.bundle_selection import (
    LauncherBundleSelection,
)
from sugarsubstitute_shared.launcher_update.models import LauncherInstallationRecord
from sugarsubstitute_shared.launcher_update.request import LauncherUpdateRequest
from sugarsubstitute_shared.launcher_update.targets import (
    launcher_bundle_target_for_key,
)
from sugarsubstitute_shared.launcher_update.versions import compare_release_versions
from sugarsubstitute_shared.process_identity import wait_for_process_exit


def apply_required_baseline_refresh(request_path: Path) -> None:
    """Promote a sealed generation into the root or retain a terminal failure."""

    path = request_path.resolve()
    request = LauncherUpdateRequest.load(path)
    root = request.install_root.resolve()
    if not path.is_relative_to(root / "launcher" / "updates"):
        raise ValueError("Baseline refresh request escapes installation updates.")
    target = launcher_bundle_target_for_key(request.target_key)
    status_store = LauncherUpdateAttemptStore(root)
    route = "required_baseline_refresh"
    status_store.save(
        LauncherUpdateAttemptStatus.create(
            version=request.version,
            phase=LauncherUpdateAttemptPhase.RUNNING,
            route=route,
        )
    )
    try:
        if request.wait_identity is not None:
            wait_for_process_exit(request.wait_identity, timeout_seconds=120.0)
        with installation_mutation(root) as operation:
            installed = LauncherInstallationRecord.load(
                root / "launcher" / "installation.json"
            )
            if installed is None or installed.target_key != target.key:
                raise ValueError(
                    "Installed launcher root has no matching version record."
                )
            if compare_release_versions(installed.version, request.version) >= 0:
                raise ValueError(
                    "Baseline refresh must not replace an equal or newer root."
                )
            selection = LauncherBundleSelection(root, target)
            selected = selection.resolve()
            if selected.version != request.version or selected.generation is None:
                raise ValueError("Baseline refresh requires the selected release.")
            selection.require_matching_staged_copy(
                selected, request.staged_bundle_dir.resolve()
            )
            LauncherBaselineTransaction().apply(request_path=path, ownership=operation)
    except BaseException as error:
        status_store.save(
            LauncherUpdateAttemptStatus.create(
                version=request.version,
                phase=LauncherUpdateAttemptPhase.FAILED,
                route=route,
                error=error,
            )
        )
        raise
    status_store.save(
        LauncherUpdateAttemptStatus.create(
            version=request.version,
            phase=LauncherUpdateAttemptPhase.COMPLETED,
            route=route,
        )
    )


__all__ = ["apply_required_baseline_refresh"]

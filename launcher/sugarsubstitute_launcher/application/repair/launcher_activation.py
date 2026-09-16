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

"""Publish repaired launcher code without replacing the recovery bootstrap."""

from __future__ import annotations

from dataclasses import dataclass

from launcher.sugarsubstitute_launcher.application.repair.models import (
    RepairReplacement,
)
from sugarsubstitute_shared.launcher_update.bundle_paths import LauncherBundlePaths

from launcher.sugarsubstitute_launcher.application.repair.request import (
    PreparedRepairRequest,
)
from sugarsubstitute_shared.launcher_update.bundle_selection import (
    LauncherBundleSelection,
    SelectedLauncherBundle,
)
from sugarsubstitute_shared.launcher_update.bundle_validation import (
    validate_launcher_bundle,
)
from sugarsubstitute_shared.launcher_update.targets import (
    launcher_bundle_target_for_key,
)


@dataclass(frozen=True, slots=True)
class PreparedLauncherRepair:
    """Bind launcher selection to the application's journaled repair transaction."""

    selection: LauncherBundleSelection
    candidate: SelectedLauncherBundle
    replacement: RepairReplacement

    @classmethod
    def prepare(cls, request: PreparedRepairRequest) -> PreparedLauncherRepair:
        """Verify the recovery baseline and seal candidate code before active mutation."""
        target = launcher_bundle_target_for_key(request.target_key)
        validate_launcher_bundle(
            bundle_dir=request.install_root,
            target=target,
            allow_installation_content=True,
        )
        selection = LauncherBundleSelection(request.install_root, target)
        candidate = selection.publish(
            request.staged_launcher_dir, version=request.version
        )
        staged_selection = (
            request.staged_launcher_dir.parent / "launcher-selection.json"
        )
        selection.stage_activation(candidate, staged_selection)
        return cls(
            selection,
            candidate,
            RepairReplacement(
                destination=LauncherBundlePaths(request.install_root).selection,
                staged_path=staged_selection,
            ),
        )

    def validate(self) -> None:
        """Require the matching launcher before application repair can commit."""
        if self.selection.resolve() != self.candidate:
            raise RuntimeError(
                "Repaired launcher selection does not match the application."
            )

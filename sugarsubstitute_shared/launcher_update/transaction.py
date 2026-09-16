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

"""Activate complete launcher generations while preserving the durable baseline."""

from __future__ import annotations

from sugarsubstitute_shared.repair_recovery.execution import recover_interrupted_repair

from sugarsubstitute_shared.installation_mutation import installation_mutation

import logging
from pathlib import Path

from sugarsubstitute_shared.launcher_update.baseline_transaction import (
    LauncherBaselineTransaction,
)
from sugarsubstitute_shared.launcher_update.bundle_selection import (
    LauncherBundleSelection,
)
from sugarsubstitute_shared.launcher_update.bundle_validation import (
    validate_launcher_bundle,
)
from sugarsubstitute_shared.launcher_update.request import LauncherUpdateRequest
from sugarsubstitute_shared.launcher_update.process import relaunch_updated_launcher
from sugarsubstitute_shared.process_identity import wait_for_process_exit
from sugarsubstitute_shared.launcher_update.targets import (
    launcher_bundle_target_for_key,
)
from sugarsubstitute_shared.windows_long_paths import operational_path

_LOGGER = logging.getLogger(__name__)


class LauncherUpdateTransactionError(RuntimeError):
    """Report an update request outside its installation-owned namespace."""


class LauncherUpdateTransaction:
    """Publish and activate a complete launcher without replacing its baseline."""

    def __init__(
        self,
        *,
        wait_timeout_seconds: float = 120.0,
    ) -> None:
        """Bind bounded handoff timing independently of bundle publication."""
        self._wait_timeout_seconds = wait_timeout_seconds

    def apply(self, *, request_path: Path) -> None:
        """Recover old journals, publish a generation, and atomically select it."""
        request_path = operational_path(request_path).resolve()
        request = LauncherUpdateRequest.load(request_path)
        target = launcher_bundle_target_for_key(request.target_key)
        root = operational_path(request.install_root).resolve()
        staged = operational_path(request.staged_bundle_dir).resolve()
        if not request_path.is_relative_to(
            root / "launcher"
        ) or not staged.is_relative_to(root / "launcher" / "updates"):
            raise LauncherUpdateTransactionError(
                "Launcher update request escapes its installation."
            )
        outgoing = request.wait_identity
        if outgoing is not None:
            wait_for_process_exit(outgoing, timeout_seconds=self._wait_timeout_seconds)
        with installation_mutation(root) as operation:
            recover_interrupted_repair(root, ownership=operation)
            LauncherBaselineTransaction().recover(
                install_root=root, target=target, ownership=operation
            )
            validate_launcher_bundle(
                bundle_dir=root, target=target, allow_installation_content=True
            )
            selection = LauncherBundleSelection(root, target)
            candidate = selection.publish(staged, version=request.version)
            selection.activate(candidate)
            _LOGGER.info(
                "Activated launcher generation",
                extra={
                    "launcher_generation": candidate.generation,
                    "launcher_version": candidate.version,
                },
            )
            request_path.unlink(missing_ok=True)
        if request.relaunch:
            relaunch_updated_launcher(root / target.executable_relative_path)


__all__ = ["LauncherUpdateTransaction", "LauncherUpdateTransactionError"]

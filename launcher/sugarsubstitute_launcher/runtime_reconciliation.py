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

"""Reconcile launcher-managed runtime state after app payload updates."""

from __future__ import annotations

from typing import Protocol

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.resources import launcher_uv_path
from launcher.sugarsubstitute_launcher.runtime import (
    RuntimeProvisioningResult,
    SubprocessRuntimeCommandRunner,
    UvManagedRuntimeInstaller,
)


class RuntimeReconciliationProgress(Protocol):
    """Receive user-visible runtime reconciliation output."""

    def append_log(self, line: str) -> None:
        """Append one runtime progress line."""


class RuntimeReconciler(Protocol):
    """Prepare the launcher-managed runtime for the installed app payload."""

    def reconcile(
        self,
        *,
        layout: InstallLayout,
        progress: RuntimeReconciliationProgress,
    ) -> RuntimeProvisioningResult:
        """Synchronize runtime dependencies for one install layout."""


class UvRuntimeReconciler:
    """Run the existing uv-backed runtime provisioning flow for updates."""

    def reconcile(
        self,
        *,
        layout: InstallLayout,
        progress: RuntimeReconciliationProgress,
    ) -> RuntimeProvisioningResult:
        """Install or refresh Python and app requirements for the payload."""

        installer = UvManagedRuntimeInstaller(
            bundled_uv_path=launcher_uv_path(),
            runner=SubprocessRuntimeCommandRunner(progress.append_log),
        )
        return installer.provision(layout=layout)

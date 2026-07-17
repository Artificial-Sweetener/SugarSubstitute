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

"""Run the production installer pipeline without constructing the setup UI."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from launcher.sugarsubstitute_launcher.first_run import (
    ContinuedInstallResult,
    DownloadedLauncherInstallResult,
    FirstRunInstaller,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.release_sources import ReleaseSource
from launcher.sugarsubstitute_launcher.resources import launcher_uv_path
from launcher.sugarsubstitute_launcher.runtime import (
    RuntimeProvisioningResult,
    SubprocessRuntimeCommandRunner,
    UvManagedRuntimeInstaller,
)


_LOGGER = logging.getLogger(__name__)


class RuntimeProvisioner(Protocol):
    """Provision the managed Python runtime for an installed app payload."""

    def provision(self, *, layout: InstallLayout) -> RuntimeProvisioningResult:
        """Return the runtime provisioned for one installation layout."""


class FirstRunInstallCoordinator(Protocol):
    """Install launcher and app artifacts from one release source."""

    def install_downloaded_launcher(
        self,
        *,
        install_root: Path,
        release_source: ReleaseSource,
        handoff_geometry: str | None = None,
        launch_installed: bool = True,
    ) -> DownloadedLauncherInstallResult:
        """Install the permanent launcher without requiring a GUI handoff."""

    def continue_install(
        self,
        *,
        layout: InstallLayout,
        release_source: ReleaseSource,
    ) -> ContinuedInstallResult:
        """Install the application payload into the prepared layout."""


@dataclass(frozen=True, slots=True)
class HeadlessInstallResult:
    """Describe a completed launcher, app, and runtime installation."""

    layout: InstallLayout
    app_version: str
    runtime_python: Path


class HeadlessInstallService:
    """Coordinate the same install stages used by the setup window."""

    def __init__(
        self,
        *,
        first_run_installer: FirstRunInstallCoordinator | None = None,
        runtime_provisioner: RuntimeProvisioner | None = None,
    ) -> None:
        """Store collaborators for launcher, payload, and runtime installation."""

        self._first_run_installer = first_run_installer or FirstRunInstaller(
            process_starter=lambda _command: None
        )
        self._runtime_provisioner = runtime_provisioner or UvManagedRuntimeInstaller(
            bundled_uv_path=launcher_uv_path(),
            runner=SubprocessRuntimeCommandRunner(_LOGGER.info),
        )

    def install(
        self,
        *,
        install_root: Path,
        release_source: ReleaseSource,
    ) -> HeadlessInstallResult:
        """Install the launcher, app payload, and managed runtime into one root."""

        launcher_result = self._first_run_installer.install_downloaded_launcher(
            install_root=install_root,
            release_source=release_source,
            launch_installed=False,
        )
        app_result = self._first_run_installer.continue_install(
            layout=launcher_result.layout,
            release_source=release_source,
        )
        runtime_result = self._runtime_provisioner.provision(layout=app_result.layout)
        return HeadlessInstallResult(
            layout=app_result.layout,
            app_version=app_result.app_version,
            runtime_python=runtime_result.python_executable,
        )

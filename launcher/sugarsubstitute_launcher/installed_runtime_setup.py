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

"""Own completion and resumption of an installed payload's runtime setup."""

from __future__ import annotations

from dataclasses import replace
import logging

from launcher.sugarsubstitute_launcher.application.installation.models import (
    InstalledApplication,
    RuntimeProvisioner,
    RuntimeProvisioningOutcome,
)
from launcher.sugarsubstitute_launcher.config import LauncherConfig
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.process import build_app_launch_command
from launcher.sugarsubstitute_launcher.update_state import LauncherUpdateState
from sugarsubstitute_shared.installation_mutation import installation_mutation

_LOGGER = logging.getLogger(__name__)


class InstalledRuntimeSetup:
    """Publish runtime completion only after provisioning and verification succeed."""

    def __init__(self, provisioner: RuntimeProvisioner) -> None:
        """Bind the runtime adapter beneath installation mutation ownership."""
        self._provisioner = provisioner

    def provision(self, *, layout: InstallLayout) -> RuntimeProvisioningOutcome:
        """Retain resumable intent on cancellation, failure, or process death."""
        with installation_mutation(layout.root):
            config = LauncherConfig.load(layout.config_path)
            replace(config, runtime_setup_pending=True).save(layout.config_path)
            result = self._provisioner.provision(layout=layout)
            replace(config, runtime_setup_pending=False).save(layout.config_path)
            _LOGGER.info("Installed runtime setup verified and completed")
            return result


def pending_runtime_application(layout: InstallLayout) -> InstalledApplication:
    """Resume installer-owned local artifacts without acquiring another release."""
    config = LauncherConfig.load(layout.config_path)
    if not config.runtime_setup_pending:
        raise ValueError("The installation has no unfinished runtime setup.")
    if (
        not layout.app_entrypoint.is_file()
        or not (layout.app_dir / "requirements.txt").is_file()
    ):
        raise ValueError("The installed runtime setup payload is incomplete.")
    state = LauncherUpdateState.load(layout.state_path)
    return InstalledApplication(
        layout=layout,
        app_command=tuple(build_app_launch_command(layout=layout)),
        app_version=state.installed_app_version or "",
        launcher_installed=True,
    )

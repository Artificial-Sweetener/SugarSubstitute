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
from pathlib import Path

from launcher.sugarsubstitute_launcher.application.installation.models import (
    ApplicationInstallationRequest,
    CompletedInstallation,
    InstallationPreparation,
)
from launcher.sugarsubstitute_launcher.application.installation.workflow import (
    InstallationWorkflow,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.release_sources import ReleaseSource


_LOGGER = logging.getLogger(__name__)


class HeadlessInstallService:
    """Adapt headless installer requests to the shared installation workflow."""

    def __init__(
        self,
        *,
        workflow: InstallationWorkflow,
    ) -> None:
        """Store the application workflow used by headless installation."""

        self._workflow = workflow

    def install(
        self,
        *,
        install_root: Path,
        release_source: ReleaseSource,
    ) -> CompletedInstallation:
        """Install the launcher, app payload, and managed runtime into one root."""

        application = self._workflow.install_application(
            ApplicationInstallationRequest(
                layout=InstallLayout.from_root(install_root),
                release_source=release_source,
                preparation=InstallationPreparation.INSTALL_LAUNCHER,
            )
        )
        result = self._workflow.provision_runtime(application)
        _LOGGER.info(
            "Completed headless installation.",
            extra={
                "install_root": str(result.application.layout.root),
                "app_version": result.application.app_version,
            },
        )
        return result

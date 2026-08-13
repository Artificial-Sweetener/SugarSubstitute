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

"""Select the release source used by initial installer invocations."""

from __future__ import annotations

from launcher.sugarsubstitute_launcher.application.installation.models import (
    ApplicationInstallationRequest,
    InstallationPreparation,
    ReleaseManifestSource,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.release_discovery import (
    discover_local_release_root,
    discover_packaged_release_root,
)
from launcher.sugarsubstitute_launcher.release_sources import (
    LocalFolderReleaseSource,
    default_production_release_source,
)


def resolve_initial_install_release_source(
    *,
    frozen_setup: bool,
) -> ReleaseManifestSource:
    """Choose the embedded, production, or source-run release channel."""

    packaged_release_root = discover_packaged_release_root()
    if packaged_release_root is not None:
        return LocalFolderReleaseSource(packaged_release_root)
    if frozen_setup:
        return default_production_release_source()
    return LocalFolderReleaseSource(discover_local_release_root())


def create_initial_installation_request(
    *,
    layout: InstallLayout,
    frozen_setup: bool,
    handoff_geometry: str | None,
) -> ApplicationInstallationRequest:
    """Build the application request for one fresh installer invocation."""

    preparation = (
        InstallationPreparation.INSTALL_LAUNCHER
        if frozen_setup
        else InstallationPreparation.PREPARE_LAYOUT
    )
    return ApplicationInstallationRequest(
        layout=layout,
        release_source=resolve_initial_install_release_source(
            frozen_setup=frozen_setup
        ),
        preparation=preparation,
        handoff_geometry=handoff_geometry,
    )


def create_continued_installation_request(
    layout: InstallLayout,
) -> ApplicationInstallationRequest:
    """Build the local-source request used by installed development launchers."""

    return ApplicationInstallationRequest(
        layout=layout,
        release_source=LocalFolderReleaseSource(discover_local_release_root()),
        preparation=InstallationPreparation.USE_EXISTING_LAYOUT,
    )

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

"""Define typed installation requests, milestones, and boundary contracts."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.manifest import ReleaseManifest


class InstallationPreparation(Enum):
    """Identify how an application installation obtains its layout."""

    INSTALL_LAUNCHER = "install_launcher"
    PREPARE_LAYOUT = "prepare_layout"
    USE_EXISTING_LAYOUT = "use_existing_layout"


class ReleaseManifestSource(Protocol):
    """Load one release manifest for installation artifacts."""

    def load_manifest(self) -> ReleaseManifest:
        """Return the release manifest exposed by this source."""


class LayoutPreparationOutcome(Protocol):
    """Expose the layout prepared by a layout installer."""

    @property
    def layout(self) -> InstallLayout:
        """Return the prepared installation layout."""


class DownloadedLauncherOutcome(Protocol):
    """Expose the layout produced by downloaded-launcher installation."""

    @property
    def layout(self) -> InstallLayout:
        """Return the installed launcher layout."""


class ApplicationPayloadOutcome(Protocol):
    """Expose the installed payload and its application command."""

    @property
    def layout(self) -> InstallLayout:
        """Return the application installation layout."""

    @property
    def app_command(self) -> Sequence[str]:
        """Return the command that starts the installed application."""

    @property
    def app_version(self) -> str:
        """Return the installed application payload version."""


class RuntimeProvisioningOutcome(Protocol):
    """Expose the Python executable prepared for an installation."""

    @property
    def python_executable(self) -> Path:
        """Return the provisioned runtime Python executable."""


class LayoutPreparer(Protocol):
    """Prepare launcher-owned filesystem layout state."""

    def prepare(self, install_root: Path) -> LayoutPreparationOutcome:
        """Prepare and return the layout for one install root."""


class ArtifactInstaller(Protocol):
    """Install launcher and application release artifacts."""

    def install_downloaded_launcher(
        self,
        *,
        install_root: Path,
        release_source: ReleaseManifestSource,
        handoff_geometry: str | None = None,
        launch_installed: bool = True,
    ) -> DownloadedLauncherOutcome:
        """Install the permanent launcher bundle into one root."""

    def continue_install(
        self,
        *,
        layout: InstallLayout,
        release_source: ReleaseManifestSource,
    ) -> ApplicationPayloadOutcome:
        """Install the application payload into a prepared layout."""


class RuntimeProvisioner(Protocol):
    """Provision the managed runtime required by an installed payload."""

    def provision(self, *, layout: InstallLayout) -> RuntimeProvisioningOutcome:
        """Provision and return the runtime for one layout."""


@dataclass(frozen=True, slots=True)
class ApplicationInstallationRequest:
    """Describe one launcher and payload installation request."""

    layout: InstallLayout
    release_source: ReleaseManifestSource
    preparation: InstallationPreparation
    handoff_geometry: str | None = None


@dataclass(frozen=True, slots=True)
class InstalledApplication:
    """Describe installed application artifacts ready for runtime setup."""

    layout: InstallLayout
    app_command: tuple[str, ...]
    app_version: str
    launcher_installed: bool


@dataclass(frozen=True, slots=True)
class CompletedInstallation:
    """Describe an installed application with a provisioned runtime."""

    application: InstalledApplication
    runtime_python: Path

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

"""Coordinate first-run launcher installation steps."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from launcher.sugarsubstitute_launcher.config import LauncherConfig
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.installation_recovery import InstallationRecovery
from launcher.sugarsubstitute_launcher.application.installation.existing_installation_rescue import (
    ExistingInstallationRescueService,
    InstallationRootKind,
)
from launcher.sugarsubstitute_launcher.installer import LayoutInstaller
from launcher.sugarsubstitute_launcher.launcher_bundle import LauncherBundleInstaller
from launcher.sugarsubstitute_launcher.manifest import ReleaseManifest
from launcher.sugarsubstitute_launcher.payload import AppPayloadInstaller
from launcher.sugarsubstitute_launcher.process import (
    build_app_launch_command,
    build_continue_install_command,
)
from launcher.sugarsubstitute_launcher.process_execution import start_detached
from launcher.sugarsubstitute_launcher.release_sources import (
    ReleaseSource,
    release_source_config_for,
)
from launcher.sugarsubstitute_launcher.trusted_metadata import TrustedMetadataState
from launcher.sugarsubstitute_launcher.update_state import LauncherUpdateState
from launcher.sugarsubstitute_launcher.update_activation import PendingUpdateActivation
from sugarsubstitute_shared.installation_mutation import installation_mutation
from sugarsubstitute_shared.application_launch_context import ApplicationLaunchIntent


ProcessStarter = Callable[[Sequence[str]], None]


@dataclass(frozen=True, slots=True)
class DownloadedLauncherInstallResult:
    """Describe the handoff from a downloaded setup exe to installed launcher."""

    layout: InstallLayout
    continue_command: list[str]
    rescued_existing_installation: bool = False
    rescue_quarantine_root: Path | None = None


@dataclass(frozen=True, slots=True)
class ContinuedInstallResult:
    """Describe the app payload installed by the installed launcher."""

    layout: InstallLayout
    app_command: list[str]
    app_version: str


class FirstRunInstaller:
    """Install the launcher shell and app payload during first-run setup."""

    def __init__(
        self,
        *,
        layout_installer: LayoutInstaller | None = None,
        launcher_bundle_installer: LauncherBundleInstaller | None = None,
        payload_installer: AppPayloadInstaller | None = None,
        process_starter: ProcessStarter = start_detached,
        existing_installation_rescue: ExistingInstallationRescueService | None = None,
    ) -> None:
        """Store collaborators used by first-run install steps."""

        self._layout_installer = layout_installer or LayoutInstaller()
        self._launcher_bundle_installer = (
            launcher_bundle_installer or LauncherBundleInstaller()
        )
        self._payload_installer = payload_installer or AppPayloadInstaller()
        self._process_starter = process_starter
        self._existing_installation_rescue = (
            existing_installation_rescue or ExistingInstallationRescueService()
        )

    def install_downloaded_launcher(
        self,
        *,
        install_root: Path,
        release_source: ReleaseSource,
        handoff_geometry: str | None = None,
        launch_installed: bool = True,
    ) -> DownloadedLauncherInstallResult:
        """Install the permanent launcher bundle into the install root and hand off."""

        with installation_mutation(install_root) as operation:
            rescue = self._existing_installation_rescue.prepare(
                InstallLayout.from_root(install_root), ownership=operation
            )
            layout_result = self._layout_installer.prepare(install_root)
            manifest = release_source.load_manifest()
            _admit_signed_metadata(layout=layout_result.layout, manifest=manifest)
            self._launcher_bundle_installer.install(
                layout=layout_result.layout,
                manifest=manifest,
                ownership=operation,
            )
            continue_command = build_continue_install_command(
                layout=layout_result.layout,
                handoff_geometry=handoff_geometry,
            )
        if launch_installed:
            self._process_starter(continue_command)
        return DownloadedLauncherInstallResult(
            layout=layout_result.layout,
            continue_command=continue_command,
            rescued_existing_installation=(
                rescue.kind is InstallationRootKind.EXISTING_SUBSTITUTE
            ),
            rescue_quarantine_root=rescue.quarantine_root,
        )

    def continue_install(
        self,
        *,
        layout: InstallLayout,
        release_source: ReleaseSource,
    ) -> ContinuedInstallResult:
        """Install the latest app payload and return the app launch command."""

        with installation_mutation(layout.root) as operation:
            InstallationRecovery(layout).recover(ownership=operation)
            layout.create_base_directories()
            manifest = release_source.load_manifest()
            _admit_signed_metadata(layout=layout, manifest=manifest)
            activation = PendingUpdateActivation.begin(
                layout=layout,
                operation=operation,
                successful_state=LauncherUpdateState.load(
                    layout.state_path
                ).with_installed_payload(
                    version=manifest.version, channel=manifest.channel
                ),
                successful_config=LauncherConfig.from_layout(
                    layout=layout,
                    channel=manifest.channel,
                    release_source=release_source_config_for(release_source),
                    runtime_setup_pending=True,
                ),
                generation_backed=True,
            )
            try:
                payload_result = self._payload_installer.install(
                    activation=activation, manifest=manifest
                )
                activation.prepare_runtime(preserve_existing=True)
                activation.commit()
            finally:
                activation.rollback()
            return ContinuedInstallResult(
                layout=layout,
                app_command=build_app_launch_command(
                    layout=layout,
                    launch_intent=ApplicationLaunchIntent.SETUP,
                ),
                app_version=payload_result.version,
            )


def _admit_signed_metadata(*, layout: InstallLayout, manifest: ReleaseManifest) -> None:
    """Persist authenticated release identity before first-run mutation proceeds."""

    metadata_version = manifest.signed_metadata_version
    signed_digest = manifest.signed_metadata_digest
    if metadata_version is None or signed_digest is None:
        return
    TrustedMetadataState.admit(
        install_root=layout.root,
        metadata_version=metadata_version,
        signed_digest=signed_digest,
    )

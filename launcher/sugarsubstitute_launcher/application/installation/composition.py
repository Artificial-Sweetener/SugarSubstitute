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

"""Compose concrete adapters for the launcher installation workflow."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from threading import Event

from launcher.sugarsubstitute_launcher.application.installation.progress import (
    InstallationProgressObserver,
)
from launcher.sugarsubstitute_launcher.application.installation.workflow import (
    InstallationWorkflow,
)
from launcher.sugarsubstitute_launcher.first_run import FirstRunInstaller
from launcher.sugarsubstitute_launcher.payload import AppPayloadInstaller
from launcher.sugarsubstitute_launcher.payload_staging import AppPayloadStager
from launcher.sugarsubstitute_launcher.downloader import AssetDownloader
from launcher.sugarsubstitute_launcher.launcher_bundle import LauncherBundleInstaller
from launcher.sugarsubstitute_launcher.installer import LayoutInstaller
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.process import (
    start_installed_launcher_handoff,
)
from launcher.sugarsubstitute_launcher.installed_runtime_setup import (
    InstalledRuntimeSetup,
)
from launcher.sugarsubstitute_launcher.runtime import UvManagedRuntimeInstaller
from launcher.sugarsubstitute_launcher.runtime_command import (
    SubprocessRuntimeCommandRunner,
)
from launcher.sugarsubstitute_launcher.runtime_resources import launcher_uv_path
from launcher.sugarsubstitute_launcher.uv_tool import VerifiedUvExecutableProvider
from sugarsubstitute_shared.launcher_update.downloader import LauncherBundleDownloader
from sugarsubstitute_shared.launcher_update.staging import LauncherBundleStager


def build_installation_workflow(
    *,
    output_callback: Callable[[str], None] | None = None,
    activity_callback: Callable[[], None] | None = None,
    progress_observer: InstallationProgressObserver | None = None,
    cancellation: Event | None = None,
    admit_installation: Callable[[InstallLayout], bool] | None = None,
    process_starter: Callable[[Sequence[str]], None] = start_installed_launcher_handoff,
) -> InstallationWorkflow:
    """Build the production installation workflow and its concrete adapters."""

    record_activity = activity_callback or (lambda: None)

    return InstallationWorkflow(
        layout_preparer=LayoutInstaller(),
        artifact_installer=FirstRunInstaller(
            launcher_bundle_installer=LauncherBundleInstaller(
                stager=LauncherBundleStager(
                    downloader=LauncherBundleDownloader(
                        progress_observer=lambda _transfer: record_activity()
                    ),
                    activity_observer=record_activity,
                )
            ),
            payload_installer=AppPayloadInstaller(
                stager=AppPayloadStager(
                    downloader=AssetDownloader(
                        progress_observer=lambda _transfer: record_activity()
                    ),
                    activity_observer=record_activity,
                )
            ),
        ),
        runtime_provisioner=InstalledRuntimeSetup(
            UvManagedRuntimeInstaller(
                uv_provider=VerifiedUvExecutableProvider(
                    bundled_uv_path=launcher_uv_path()
                ),
                runner=SubprocessRuntimeCommandRunner(
                    output_callback, cancellation=cancellation
                ),
            )
        ),
        process_starter=process_starter,
        progress_observer=progress_observer,
        admit_installation=admit_installation,
    )

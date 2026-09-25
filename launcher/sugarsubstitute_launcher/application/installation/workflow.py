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

"""Own launcher, payload, runtime, and setup-handoff installation sequencing."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import secrets

from launcher.sugarsubstitute_launcher.application.installation.models import (
    ApplicationInstallationRequest,
    ArtifactInstaller,
    CompletedInstallation,
    InstallationPreparation,
    InstallationAlreadyPresented,
    InstalledApplication,
    LayoutPreparer,
    RuntimeProvisioner,
)
from launcher.sugarsubstitute_launcher.application.installation.progress import (
    InstallationProgressObserver,
    InstallationProgressReporter,
    InstallationStage,
)
from launcher.sugarsubstitute_launcher.application.repair.session_recovery import (
    SessionRescuer,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.session_recovery import (
    SessionRecoveryResult,
    SessionRecoveryState,
)


class InstallationWorkflow:
    """Coordinate installer stages independently from GUI and headless adapters."""

    def __init__(
        self,
        *,
        layout_preparer: LayoutPreparer,
        artifact_installer: ArtifactInstaller,
        runtime_provisioner: RuntimeProvisioner,
        process_starter: Callable[[Sequence[str]], None],
        progress_observer: InstallationProgressObserver | None = None,
        admit_installation: Callable[[InstallLayout], bool] | None = None,
        session_rescuer: SessionRescuer | None = None,
    ) -> None:
        """Store the adapters used by the installation use case."""

        self._layout_preparer = layout_preparer
        self._artifact_installer = artifact_installer
        self._runtime_provisioner = runtime_provisioner
        self._process_starter = process_starter
        self._progress = InstallationProgressReporter(progress_observer)
        self._admit_installation = admit_installation
        self._session_rescuer = session_rescuer

    def install_application(
        self,
        request: ApplicationInstallationRequest,
    ) -> InstalledApplication:
        """Prepare the requested layout and install its application payload."""

        self._progress.publish(InstallationStage.PREPARATION)
        if self._admit_installation is not None and not self._admit_installation(
            request.layout
        ):
            raise InstallationAlreadyPresented()
        launcher_installed = False
        rescued_existing_installation = False
        if request.preparation is InstallationPreparation.INSTALL_LAUNCHER:
            launcher_result = self._artifact_installer.install_downloaded_launcher(
                install_root=request.layout.root,
                release_source=request.release_source,
                handoff_geometry=request.handoff_geometry,
                launch_installed=False,
            )
            layout = launcher_result.layout
            launcher_installed = True
            rescued_existing_installation = (
                launcher_result.rescued_existing_installation
            )
        elif request.preparation is InstallationPreparation.PREPARE_LAYOUT:
            layout = self._layout_preparer.prepare(request.layout.root).layout
        else:
            layout = request.layout

        self._progress.publish(InstallationStage.PREPARATION, finished=True)
        self._progress.publish(InstallationStage.APPLICATION)
        payload_result = self._artifact_installer.continue_install(
            layout=layout,
            release_source=request.release_source,
        )
        self._progress.publish(InstallationStage.APPLICATION, finished=True)
        return InstalledApplication(
            layout=payload_result.layout,
            app_command=tuple(payload_result.app_command),
            app_version=payload_result.app_version,
            launcher_installed=launcher_installed,
            rescued_existing_installation=rescued_existing_installation,
        )

    def provision_runtime(
        self,
        application: InstalledApplication,
    ) -> CompletedInstallation:
        """Provision the managed runtime for installed application artifacts."""

        self._progress.publish(InstallationStage.RUNTIME)
        runtime_result = self._runtime_provisioner.provision(layout=application.layout)
        session_recovery = SessionRecoveryResult(SessionRecoveryState.NO_SESSION)
        if application.rescued_existing_installation:
            if self._session_rescuer is None:
                raise RuntimeError(
                    "Existing-installation rescue requires a session reconciler."
                )
            session_recovery = self._session_rescuer.reconcile(
                layout=application.layout,
                recovery_root=(
                    application.layout.root
                    / ".repair"
                    / "session-recovery"
                    / f"installer-{secrets.token_hex(16)}"
                ),
            )
        self._progress.publish(InstallationStage.RUNTIME, finished=True)
        return CompletedInstallation(
            application=application,
            runtime_python=runtime_result.python_executable,
            session_recovery=session_recovery,
        )

    def start_setup(
        self,
        command: Sequence[str],
    ) -> None:
        """Start the installed application setup process."""

        self._progress.publish(InstallationStage.HANDOFF)
        self._process_starter(command)
        self._progress.publish(InstallationStage.HANDOFF, finished=True)

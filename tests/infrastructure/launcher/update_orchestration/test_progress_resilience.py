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

"""Prove optional update feedback cannot change launcher update outcomes."""

from __future__ import annotations

from pathlib import Path

from launcher.sugarsubstitute_launcher.config import LauncherConfig
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.manifest import ReleaseAsset, ReleaseManifest
from launcher.sugarsubstitute_launcher.payload_models import AppPayloadInstallResult
from launcher.sugarsubstitute_launcher.runtime_models import RuntimeProvisioningResult
from launcher.sugarsubstitute_launcher.update_orchestrator import (
    LauncherUpdateOrchestrator,
)
from launcher.sugarsubstitute_launcher.update_state import LauncherUpdateState
from sugarsubstitute_shared.launch_splash import SplashActivity


def test_disconnected_splash_does_not_block_current_installed_app(
    tmp_path: Path,
) -> None:
    """Launch the current app even when its splash stops acknowledging logs."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    config = LauncherConfig.from_layout(layout=layout)
    LauncherUpdateState(installed_app_version="0.4.0").save(layout.state_path)

    result = LauncherUpdateOrchestrator().run(
        layout=layout,
        config=config,
        release_source=_ReleaseSource(_manifest(version="0.4.0")),
        no_update_check=False,
        progress=_DisconnectedProgress(),
    )

    assert result.checked_manifest is True
    assert result.installed_update is False
    assert result.skipped_reason == "installed_current"
    assert result.failure_reason is None


def test_disconnected_splash_does_not_discard_prepared_update(
    tmp_path: Path,
) -> None:
    """Return activation authority after update feedback delivery fails."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    config = LauncherConfig.from_layout(layout=layout)

    result = LauncherUpdateOrchestrator(
        payload_installer=_PayloadInstaller(version="0.4.0"),
        runtime_reconciler=_RuntimeReconciler(),
    ).run(
        layout=layout,
        config=config,
        release_source=_ReleaseSource(_manifest(version="0.4.0")),
        no_update_check=False,
        progress=_DisconnectedProgress(),
    )

    assert result.checked_manifest is True
    assert result.installed_update is True
    assert result.failure_reason is None
    assert result.pending_activation is not None
    assert result.attempted_version == "0.4.0"


def _manifest(*, version: str) -> ReleaseManifest:
    """Create one minimal stable release manifest."""

    return ReleaseManifest(
        schema_version=1,
        channel="stable",
        version=version,
        minimum_launcher_version="0.1.0",
        app=ReleaseAsset(
            filename=f"SugarSubstitute-app-v{version}.zip",
            url="file:///release.zip",
            sha256="0" * 64,
            size_bytes=1,
        ),
        launchers={},
        installers={},
    )


class _ReleaseSource:
    """Return one configured release manifest."""

    def __init__(self, manifest: ReleaseManifest) -> None:
        """Store the manifest."""

        self._manifest = manifest

    def load_manifest(self) -> ReleaseManifest:
        """Return the configured manifest."""

        return self._manifest


class _PayloadInstaller:
    """Return a successful payload installation."""

    def __init__(self, *, version: str) -> None:
        """Store the installed version."""

        self._version = version

    def install(
        self,
        *,
        layout: InstallLayout,
        manifest: ReleaseManifest,
    ) -> AppPayloadInstallResult:
        """Return the prepared payload result."""

        _ = manifest
        return AppPayloadInstallResult(version=self._version, app_dir=layout.app_dir)


class _RuntimeReconciler:
    """Complete runtime reconciliation without external work."""

    def reconcile(
        self,
        *,
        layout: InstallLayout,
        progress: object,
    ) -> RuntimeProvisioningResult:
        """Return one prepared runtime result."""

        _ = progress
        return RuntimeProvisioningResult(
            python_executable=layout.runtime_python,
            requirements_path=layout.app_dir / "requirements.txt",
        )


class _DisconnectedProgress:
    """Represent a splash host that rejects every progress message."""

    def append_log(self, line: str) -> None:
        """Reject one update log message."""

        _ = line
        raise OSError("splash disconnected")

    def start_activity(self, activity: SplashActivity) -> None:
        """Reject one update activity message."""

        _ = activity
        raise OSError("splash disconnected")

    def clear_activity(self) -> None:
        """Reject one activity-clear message."""

        raise OSError("splash disconnected")

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

"""Tests for packaged connectivity and headless installation orchestration."""

from __future__ import annotations

import hashlib
from pathlib import Path

from launcher.sugarsubstitute_launcher.connectivity import (
    ReleaseConnectivityVerifier,
)
from launcher.sugarsubstitute_launcher.first_run import (
    ContinuedInstallResult,
    DownloadedLauncherInstallResult,
)
from launcher.sugarsubstitute_launcher.headless_install import HeadlessInstallService
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.manifest import ReleaseAsset, ReleaseManifest
from launcher.sugarsubstitute_launcher.platforms import detect_launcher_target
from launcher.sugarsubstitute_launcher.release_sources import ReleaseSource
from launcher.sugarsubstitute_launcher.runtime import RuntimeProvisioningResult


class StaticReleaseSource:
    """Return one deterministic manifest without network access."""

    def __init__(self, manifest: ReleaseManifest) -> None:
        """Store the manifest returned by the source."""

        self._manifest = manifest

    def load_manifest(self) -> ReleaseManifest:
        """Return the configured manifest."""

        return self._manifest


class RecordingFirstRunInstaller:
    """Record launcher and app install orchestration calls."""

    def __init__(self, layout: InstallLayout) -> None:
        """Store the layout returned by both install stages."""

        self._layout = layout
        self.calls: list[str] = []

    def install_downloaded_launcher(
        self,
        *,
        install_root: Path,
        release_source: ReleaseSource,
        handoff_geometry: str | None = None,
        launch_installed: bool = True,
    ) -> DownloadedLauncherInstallResult:
        """Record launcher installation without starting another process."""

        assert install_root == self._layout.root
        assert release_source.load_manifest().version == "1.2.3"
        assert handoff_geometry is None
        assert launch_installed is False
        self.calls.append("launcher")
        return DownloadedLauncherInstallResult(
            layout=self._layout,
            continue_command=[],
        )

    def continue_install(
        self,
        *,
        layout: InstallLayout,
        release_source: ReleaseSource,
    ) -> ContinuedInstallResult:
        """Record application installation into the prepared layout."""

        assert layout == self._layout
        assert release_source.load_manifest().version == "1.2.3"
        self.calls.append("app")
        return ContinuedInstallResult(
            layout=self._layout,
            app_command=[],
            app_version="1.2.3",
        )


class RecordingRuntimeProvisioner:
    """Record runtime provisioning for the installed app layout."""

    def __init__(self, python_executable: Path) -> None:
        """Store the runtime executable returned by provisioning."""

        self._python_executable = python_executable
        self.layouts: list[InstallLayout] = []

    def provision(self, *, layout: InstallLayout) -> RuntimeProvisioningResult:
        """Return a deterministic managed-runtime result."""

        self.layouts.append(layout)
        return RuntimeProvisioningResult(
            python_executable=self._python_executable,
            requirements_path=layout.app_dir / "requirements.txt",
        )


def test_release_connectivity_verifier_downloads_and_hashes_release_assets(
    tmp_path: Path,
) -> None:
    """Connectivity proof should cover app and launcher download paths."""

    payload = tmp_path / "payload.zip"
    payload.write_bytes(b"verified payload")
    manifest = _manifest_for(payload)

    ReleaseConnectivityVerifier().verify(release_source=StaticReleaseSource(manifest))


def test_headless_install_runs_launcher_app_and_runtime_stages(tmp_path: Path) -> None:
    """Headless mode should execute the complete production install sequence."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    payload = tmp_path / "payload.zip"
    payload.write_bytes(b"payload")
    release_source = StaticReleaseSource(_manifest_for(payload))
    first_run = RecordingFirstRunInstaller(layout)
    runtime = RecordingRuntimeProvisioner(layout.runtime_python)

    result = HeadlessInstallService(
        first_run_installer=first_run,
        runtime_provisioner=runtime,
    ).install(
        install_root=layout.root,
        release_source=release_source,
    )

    assert first_run.calls == ["launcher", "app"]
    assert runtime.layouts == [layout]
    assert result.layout == layout
    assert result.app_version == "1.2.3"
    assert result.runtime_python == layout.runtime_python


def _manifest_for(payload: Path) -> ReleaseManifest:
    """Return a minimal manifest referencing one local app payload."""

    return ReleaseManifest(
        schema_version=1,
        channel="test",
        version="1.2.3",
        minimum_launcher_version="0.1.0",
        app=ReleaseAsset(
            filename=payload.name,
            url=payload.as_uri(),
            sha256=hashlib.sha256(payload.read_bytes()).hexdigest(),
            size_bytes=payload.stat().st_size,
        ),
        launchers={
            detect_launcher_target().key: ReleaseAsset(
                filename=f"launcher-{payload.name}",
                url=payload.as_uri(),
                sha256=hashlib.sha256(payload.read_bytes()).hexdigest(),
                size_bytes=payload.stat().st_size,
            )
        },
        installers={},
    )

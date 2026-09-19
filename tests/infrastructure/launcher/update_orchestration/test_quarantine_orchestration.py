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

"""Verify failed immutable payloads do not enter an automatic retry loop."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from launcher.sugarsubstitute_launcher.config import LauncherConfig
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.manifest import ReleaseAsset, ReleaseManifest
from launcher.sugarsubstitute_launcher.payload_models import (
    AppPayloadInstallResult,
    StagedAppPayload,
)
from launcher.sugarsubstitute_launcher.runtime_models import RuntimeProvisioningResult
from launcher.sugarsubstitute_launcher.update_activation import PendingUpdateActivation
from launcher.sugarsubstitute_launcher.update_orchestrator import (
    LauncherUpdateOrchestrator,
)


def test_failed_exact_payload_is_not_retried_automatically(tmp_path: Path) -> None:
    """A deterministic candidate failure should quarantine its version and digest."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    config = LauncherConfig.from_layout(layout=layout)
    manifest = _manifest()
    installer = _PayloadInstaller()
    orchestrator = LauncherUpdateOrchestrator(
        payload_installer=installer,
        runtime_reconciler=_FailingRuntimeReconciler(),
        now=lambda: datetime(2026, 9, 18, 12, tzinfo=UTC),
    )

    first = orchestrator.run(
        layout=layout,
        config=config,
        release_source=_ReleaseSource(manifest),
        no_update_check=False,
    )
    second = orchestrator.run(
        layout=layout,
        config=config,
        release_source=_ReleaseSource(manifest),
        no_update_check=False,
    )

    assert first.failure_reason == "RuntimeError"
    assert second.skipped_reason == "candidate_quarantined"
    assert second.attempted_version == "0.4.0"
    assert installer.install_count == 1


def _manifest() -> ReleaseManifest:
    """Return one immutable candidate target."""

    return ReleaseManifest(
        schema_version=1,
        channel="stable",
        version="0.4.0",
        minimum_launcher_version="0.1.0",
        app=ReleaseAsset(
            filename="app.zip",
            url="file:///app.zip",
            sha256="0" * 64,
            size_bytes=1,
        ),
        launchers={},
        installers={},
    )


class _ReleaseSource:
    """Return one exact manifest."""

    def __init__(self, manifest: ReleaseManifest) -> None:
        """Store the manifest."""

        self._manifest = manifest

    def load_manifest(self) -> ReleaseManifest:
        """Return the stored manifest."""

        return self._manifest


class _PayloadInstaller:
    """Promote one minimal app payload and count calls."""

    def __init__(self) -> None:
        """Initialize the call count."""

        self.install_count = 0

    def install(
        self,
        *,
        activation: PendingUpdateActivation,
        manifest: ReleaseManifest,
    ) -> AppPayloadInstallResult:
        """Promote a transaction-owned empty app directory."""

        self.install_count += 1
        activation.staging_directory.mkdir(parents=True)
        return activation.promote_app(
            StagedAppPayload(
                version=manifest.version,
                staging_dir=activation.staging_directory,
            )
        )


class _FailingRuntimeReconciler:
    """Inject one deterministic preparation failure."""

    def reconcile(
        self, *, layout: InstallLayout, progress: object
    ) -> RuntimeProvisioningResult:
        """Fail before the candidate is selected."""

        _ = layout
        _ = progress
        raise RuntimeError("runtime unavailable")

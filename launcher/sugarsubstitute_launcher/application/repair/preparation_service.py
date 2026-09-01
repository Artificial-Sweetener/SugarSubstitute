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

"""Stage exact-version application and launcher artifacts for detached repair."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from launcher.sugarsubstitute_launcher.application.installation.models import (
    ReleaseManifestSource,
)
from launcher.sugarsubstitute_launcher.application.repair.models import RepairScope
from launcher.sugarsubstitute_launcher.application.repair.integrity import (
    directory_tree_sha256,
)
from launcher.sugarsubstitute_launcher.application.repair.request import (
    PreparedRepairRequest,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.manifest import ReleaseManifest
from launcher.sugarsubstitute_launcher.payload_models import StagedAppPayload
from launcher.sugarsubstitute_launcher.payload_staging import AppPayloadStager
from sugarsubstitute_shared.launcher_update.models import LauncherBundleAsset
from sugarsubstitute_shared.launcher_update.staging import LauncherBundleStager
from sugarsubstitute_shared.launcher_update.targets import (
    LauncherBundleTarget,
    launcher_bundle_target_for_key,
)
from sugarsubstitute_shared.launcher_version import safe_launcher_version


class RepairPreparationError(RuntimeError):
    """Report a repair whose exact artifacts cannot be prepared safely."""


class AppPayloadStagerProtocol(Protocol):
    """Stage a verified application release without active mutations."""

    def stage(
        self,
        *,
        layout: InstallLayout,
        manifest: ReleaseManifest,
        destination_dir: Path,
    ) -> StagedAppPayload:
        """Return the verified staged payload."""


class LauncherBundleStagerProtocol(Protocol):
    """Stage a verified launcher bundle without creating a promotion request."""

    def stage_bundle(
        self,
        *,
        install_root: Path,
        version: str,
        target: LauncherBundleTarget,
        asset: LauncherBundleAsset,
        destination_dir: Path,
    ) -> Path:
        """Return the verified staged launcher directory."""


@dataclass(frozen=True, slots=True)
class RepairPreparation:
    """Describe persisted exact-version repair artifacts ready for handoff."""

    request: PreparedRepairRequest
    request_path: Path


class RepairPreparationService:
    """Prepare every immutable release artifact before repair mutation begins."""

    def __init__(
        self,
        *,
        app_stager: AppPayloadStagerProtocol | None = None,
        launcher_stager: LauncherBundleStagerProtocol | None = None,
    ) -> None:
        """Store the two checksum-verifying staging adapters."""

        self._app_stager = app_stager or AppPayloadStager()
        self._launcher_stager = launcher_stager or LauncherBundleStager()

    def prepare_application_repair(
        self,
        *,
        layout: InstallLayout,
        release_source: ReleaseManifestSource,
        expected_version: str,
    ) -> RepairPreparation:
        """Stage an exact application repair and persist its detached request."""

        version = safe_launcher_version(expected_version)
        manifest = release_source.load_manifest()
        if manifest.version != version:
            raise RepairPreparationError(
                "Repair manifest version mismatch: "
                f"expected {version}, got {manifest.version}."
            )
        return self._prepare_manifest(layout=layout, manifest=manifest)

    def prepare_bound_application_repair(
        self,
        *,
        layout: InstallLayout,
        release_source: ReleaseManifestSource,
        scope: RepairScope = RepairScope.APPLICATION,
    ) -> RepairPreparation:
        """Stage the exact release bound to this installer source."""

        manifest = release_source.load_manifest()
        safe_launcher_version(manifest.version)
        return self._prepare_manifest(layout=layout, manifest=manifest, scope=scope)

    def _prepare_manifest(
        self,
        *,
        layout: InstallLayout,
        manifest: ReleaseManifest,
        scope: RepairScope = RepairScope.APPLICATION,
    ) -> RepairPreparation:
        """Stage one already-bound manifest without reloading mutable metadata."""

        version = safe_launcher_version(manifest.version)
        release_asset = manifest.launcher_for(layout.target)
        if release_asset is None:
            raise RepairPreparationError(
                f"Repair manifest has no launcher for {layout.target.key}."
            )
        staging_root = layout.root / ".repair" / "staging" / version
        staged_app = self._app_stager.stage(
            layout=layout,
            manifest=manifest,
            destination_dir=staging_root / "app",
        )
        launcher_target = launcher_bundle_target_for_key(layout.target.key)
        staged_launcher = self._launcher_stager.stage_bundle(
            install_root=layout.root,
            version=version,
            target=launcher_target,
            asset=LauncherBundleAsset(
                filename=release_asset.filename,
                url=release_asset.url,
                sha256=release_asset.sha256,
                size_bytes=release_asset.size_bytes,
            ),
            destination_dir=staging_root / "launcher",
        )
        request = PreparedRepairRequest(
            install_root=layout.root,
            scope=scope,
            version=version,
            channel=manifest.channel,
            target_key=layout.target.key,
            staged_app_dir=staged_app.staging_dir,
            staged_launcher_dir=staged_launcher,
            staged_app_sha256=directory_tree_sha256(staged_app.staging_dir),
            staged_launcher_sha256=directory_tree_sha256(staged_launcher),
        )
        request_path = layout.root / ".repair" / "prepared.json"
        request.save(request_path)
        return RepairPreparation(request=request, request_path=request_path)


__all__ = [
    "RepairPreparation",
    "RepairPreparationError",
    "RepairPreparationService",
]

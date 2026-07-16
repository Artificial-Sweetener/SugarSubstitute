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

"""Install first-run launcher bundles through the shared update transaction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.manifest import ReleaseManifest
from launcher.sugarsubstitute_launcher.payload import PayloadInstallError
from sugarsubstitute_shared.launcher_update.models import LauncherBundleAsset
from sugarsubstitute_shared.launcher_update.staging import LauncherBundleStager
from sugarsubstitute_shared.launcher_update.targets import (
    launcher_bundle_target_for_key,
)
from sugarsubstitute_shared.launcher_update.transaction import (
    LauncherUpdateTransaction,
)


@dataclass(frozen=True, slots=True)
class LauncherBundleInstallResult:
    """Describe an installed launcher bundle."""

    executable_path: Path
    support_dir: Path


class LauncherBundleInstaller:
    """Install a first-run bundle through the authoritative safe replacement path."""

    def __init__(
        self,
        *,
        stager: LauncherBundleStager | None = None,
        transaction: LauncherUpdateTransaction | None = None,
    ) -> None:
        """Store shared staging and promotion collaborators."""

        self._stager = stager or LauncherBundleStager()
        self._transaction = transaction or LauncherUpdateTransaction()

    def install(
        self,
        *,
        layout: InstallLayout,
        manifest: ReleaseManifest,
    ) -> LauncherBundleInstallResult:
        """Install the target launcher and persist its installed version."""

        release_asset = manifest.launcher_for(layout.target)
        if release_asset is None:
            raise PayloadInstallError(
                "Release manifest does not include a launcher bundle."
            )
        request_path = self._stager.stage(
            install_root=layout.root,
            version=manifest.version,
            target=launcher_bundle_target_for_key(layout.target.key),
            asset=LauncherBundleAsset(
                filename=release_asset.filename,
                url=release_asset.url,
                sha256=release_asset.sha256,
                size_bytes=release_asset.size_bytes,
            ),
        )
        self._transaction.apply(request_path=request_path)
        return LauncherBundleInstallResult(
            executable_path=layout.executable_path,
            support_dir=layout.launcher_support_path,
        )


__all__ = ["LauncherBundleInstallResult", "LauncherBundleInstaller"]

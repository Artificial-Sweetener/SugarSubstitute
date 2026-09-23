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

"""Prepare compatible launcher replacements without modifying the installed app."""

from __future__ import annotations
from pathlib import Path
from typing import Protocol
from urllib.error import URLError
from launcher.sugarsubstitute_launcher import __version__ as LAUNCHER_VERSION
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.manifest import ReleaseManifest
from launcher.sugarsubstitute_launcher.localized_text import launcher_text
from launcher.sugarsubstitute_launcher.update_progress import LauncherUpdateProgress
from launcher.sugarsubstitute_launcher.update_activity import launcher_update_activity
from sugarsubstitute_shared.launcher_update.models import LauncherBundleAsset
from sugarsubstitute_shared.launcher_update.staging import LauncherBundleStager
from sugarsubstitute_shared.launcher_update.downloader import LauncherBundleDownloader
from sugarsubstitute_shared.launcher_update.targets import (
    LauncherBundleTarget,
    launcher_bundle_target_for_key,
)
from sugarsubstitute_shared.launcher_update.versions import compare_release_versions


class LauncherMinimumVersionError(RuntimeError):
    """Report a required launcher update that cannot be completed safely."""


class LauncherBundleStagerProtocol(Protocol):
    """Stage a verified launcher bundle for detached replacement."""

    def stage(
        self,
        *,
        install_root: Path,
        version: str,
        target: LauncherBundleTarget,
        asset: LauncherBundleAsset,
    ) -> Path:
        """Return the pending update request path."""


class LauncherUpdatePreparation:
    """Own launcher-version admission and verified bundle staging."""

    def __init__(
        self,
        *,
        stager: LauncherBundleStagerProtocol | None = None,
        launcher_version: str = LAUNCHER_VERSION,
    ) -> None:
        """Bind the running launcher version and external bundle acquisition boundary."""
        self._stager = stager
        self._launcher_version = launcher_version

    def stage(
        self,
        *,
        layout: InstallLayout,
        manifest: ReleaseManifest,
        progress: LauncherUpdateProgress,
    ) -> Path | None:
        """Stage a newer launcher or enforce the manifest minimum version."""

        version_comparison = compare_release_versions(
            self._launcher_version,
            manifest.version,
        )
        minimum_comparison = compare_release_versions(
            self._launcher_version,
            manifest.minimum_launcher_version,
        )
        if minimum_comparison < 0 and version_comparison >= 0:
            raise LauncherMinimumVersionError(
                "The release manifest requires a launcher version newer than its "
                "published launcher bundle."
            )
        if version_comparison >= 0:
            return None
        release_asset = manifest.launcher_for(layout.target)
        if release_asset is None:
            if minimum_comparison < 0:
                raise LauncherMinimumVersionError(
                    "This release requires a newer launcher, but its launcher bundle "
                    f"is missing for {layout.target.key}."
                )
            return None
        if not layout.runtime_python.is_file():
            error_message = (
                "The managed app runtime is unavailable for launcher replacement."
            )
            if minimum_comparison < 0:
                raise LauncherMinimumVersionError(error_message)
            raise RuntimeError(error_message)
        activity = launcher_update_activity(manifest.version)
        progress.append_log(activity.initial_text)
        progress.start_activity(activity)
        try:
            stager = self._stager or LauncherBundleStager(
                downloader=LauncherBundleDownloader(
                    progress_observer=lambda _transfer: progress.record_activity()
                ),
                activity_observer=progress.record_activity,
            )
            request_path = stager.stage(
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
        except (ConnectionError, TimeoutError, URLError):
            progress.clear_activity()
            raise
        except Exception as error:
            progress.clear_activity()
            if minimum_comparison < 0:
                raise LauncherMinimumVersionError(
                    "The required launcher update could not be staged."
                ) from error
            raise
        progress.clear_activity()
        progress.append_log(
            launcher_text("The launcher will restart to finish updating.")
        )
        return request_path

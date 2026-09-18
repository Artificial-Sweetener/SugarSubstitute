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

"""Stage verified payloads and delegate publication to the activation owner."""

from __future__ import annotations


from launcher.sugarsubstitute_launcher.downloader import AssetDownloader
from launcher.sugarsubstitute_launcher.update_activation import PendingUpdateActivation
from launcher.sugarsubstitute_launcher.manifest import ReleaseManifest
from launcher.sugarsubstitute_launcher.payload_models import (
    AppPayloadInstallResult,
)
from launcher.sugarsubstitute_launcher.payload_staging import AppPayloadStager


class AppPayloadInstaller:
    """Compose payload staging and promotion for normal install/update callers."""

    def __init__(
        self,
        *,
        downloader: AssetDownloader | None = None,
        stager: AppPayloadStager | None = None,
    ) -> None:
        """Store the payload staging boundary."""

        if downloader is not None and stager is not None:
            raise TypeError("Pass downloader or stager, not both.")
        self._stager = stager or AppPayloadStager(downloader=downloader)

    def install(
        self,
        *,
        activation: PendingUpdateActivation,
        manifest: ReleaseManifest,
    ) -> AppPayloadInstallResult:
        """Stage and promote one manifest payload through the normal install path."""

        staged = self._stager.stage(
            layout=activation.layout,
            manifest=manifest,
            destination_dir=activation.staging_directory,
        )
        return activation.promote_app(staged)


__all__ = ["AppPayloadInstaller"]

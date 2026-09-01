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

"""Promote verified application payloads into the installed application slot."""

from __future__ import annotations

import logging
from pathlib import Path
import shutil

from launcher.sugarsubstitute_launcher.downloader import AssetDownloader
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.manifest import ReleaseManifest
from launcher.sugarsubstitute_launcher.payload_models import (
    AppPayloadInstallResult,
    StagedAppPayload,
)
from launcher.sugarsubstitute_launcher.payload_staging import AppPayloadStager

_LOGGER = logging.getLogger(__name__)


class AppPayloadPromoter:
    """Atomically promote a verified staged payload with immediate rollback."""

    def promote(
        self,
        *,
        layout: InstallLayout,
        staged: StagedAppPayload,
    ) -> AppPayloadInstallResult:
        """Replace the active payload and restore it if promotion fails."""

        previous_dir = layout.root / "app_previous"
        _remove_directory(previous_dir)
        previous_created = False
        if layout.app_dir.exists():
            layout.app_dir.replace(previous_dir)
            previous_created = True
        try:
            staged.staging_dir.replace(layout.app_dir)
        except OSError:
            if previous_created and not layout.app_dir.exists():
                previous_dir.replace(layout.app_dir)
            raise
        _LOGGER.info("Promoted app payload.", extra={"version": staged.version})
        return AppPayloadInstallResult(
            version=staged.version,
            app_dir=layout.app_dir,
        )


class AppPayloadInstaller:
    """Compose payload staging and promotion for normal install/update callers."""

    def __init__(
        self,
        *,
        downloader: AssetDownloader | None = None,
        stager: AppPayloadStager | None = None,
        promoter: AppPayloadPromoter | None = None,
    ) -> None:
        """Store the separate staging and promotion owners."""

        if downloader is not None and stager is not None:
            raise TypeError("Pass downloader or stager, not both.")
        self._stager = stager or AppPayloadStager(downloader=downloader)
        self._promoter = promoter or AppPayloadPromoter()

    def install(
        self,
        *,
        layout: InstallLayout,
        manifest: ReleaseManifest,
    ) -> AppPayloadInstallResult:
        """Stage and promote one manifest payload through the normal install path."""

        staged = self._stager.stage(
            layout=layout,
            manifest=manifest,
            destination_dir=layout.root / "app_next",
        )
        return self._promoter.promote(layout=layout, staged=staged)


def _remove_directory(path: Path) -> None:
    """Remove one installer-owned rollback directory when present."""

    if path.exists():
        shutil.rmtree(path)


__all__ = ["AppPayloadInstaller", "AppPayloadPromoter"]

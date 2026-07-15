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

"""Coordinate verified standalone environment provisioning for new workspaces."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from substitute.infrastructure.comfy.standalone_environment.catalog_client import (
    StandaloneEnvironmentCatalogClient,
)
from substitute.infrastructure.comfy.standalone_environment.downloader import (
    DownloadProgressCallback,
    StandaloneArtifactDownloader,
)
from substitute.infrastructure.comfy.standalone_environment.directory_copy import (
    DirectoryCopyProgress,
)
from substitute.infrastructure.comfy.standalone_environment.environment_builder import (
    StandaloneVirtualEnvironmentBuilder,
)
from substitute.infrastructure.comfy.standalone_environment.extractor import (
    StandaloneEnvironmentExtractor,
)
from substitute.infrastructure.comfy.standalone_environment.extraction_process import (
    SevenZipExtractionProgress,
)
from substitute.infrastructure.comfy.standalone_environment.migration import (
    StandaloneWorkspaceMigrator,
)
from substitute.infrastructure.comfy.standalone_environment.models import (
    StandaloneArtifactError,
    StandaloneVariantId,
)


ProvisioningLogCallback = Callable[[str], None]


class StandaloneEnvironmentProvisioner:
    """Coordinate catalog, acquisition, extraction, promotion, and venv hydration."""

    def __init__(
        self,
        *,
        catalog: StandaloneEnvironmentCatalogClient | None = None,
        downloader: StandaloneArtifactDownloader | None = None,
        extractor: StandaloneEnvironmentExtractor | None = None,
        migrator: StandaloneWorkspaceMigrator | None = None,
        environment_builder: StandaloneVirtualEnvironmentBuilder | None = None,
    ) -> None:
        """Store focused collaborators for the provisioning transaction."""

        self._catalog = catalog or StandaloneEnvironmentCatalogClient()
        self._downloader = downloader or StandaloneArtifactDownloader()
        self._extractor = extractor or StandaloneEnvironmentExtractor()
        self._migrator = migrator or StandaloneWorkspaceMigrator()
        self._environment_builder = (
            environment_builder or StandaloneVirtualEnvironmentBuilder()
        )

    def provision(
        self,
        *,
        workspace: Path,
        variant: StandaloneVariantId,
        cache_root: Path | None = None,
        on_log: ProvisioningLogCallback | None = None,
        on_download_progress: DownloadProgressCallback | None = None,
    ) -> Path:
        """Provision a new workspace from checksum-verified relocatable assets."""

        self._emit(on_log, f"Resolving standalone environment {variant.value}.")
        release = self._catalog.resolve(variant)
        selected_cache = cache_root or (
            workspace.parent / ".sugarsubstitute-cache" / "standalone"
        )
        self._emit(
            on_log,
            f"Downloading {release.total_size_bytes} verified environment bytes.",
        )
        artifacts = self._downloader.download(
            release,
            selected_cache,
            on_progress=on_download_progress,
        )
        extraction_root = workspace.parent / (
            f".{workspace.name}.standalone-extract-{uuid4().hex}"
        )
        try:
            self._emit(on_log, "Extracting the verified standalone environment.")
            extraction_progress = _ExtractionProgressLog(on_log)
            self._extractor.extract(
                release,
                artifacts,
                extraction_root,
                on_extraction_progress=extraction_progress.publish,
            )
            layout = self._migrator.promote(extraction_root, workspace, release)
            self._emit(on_log, "Hydrating the managed Comfy Python environment.")
            copy_progress = _CopyProgressLog(on_log)
            return self._environment_builder.build(
                layout,
                on_progress=copy_progress.publish,
            )
        except StandaloneArtifactError:
            shutil.rmtree(extraction_root, ignore_errors=True)
            shutil.rmtree(workspace, ignore_errors=True)
            raise

    @staticmethod
    def _emit(
        callback: ProvisioningLogCallback | None,
        message: str,
    ) -> None:
        """Emit one provisioning status line when requested."""

        if callback is not None:
            callback(message)


class _CopyProgressLog:
    """Translate package-copy progress into throttled user-visible log lines."""

    def __init__(self, callback: ProvisioningLogCallback | None) -> None:
        """Store the output callback and last published percentage."""

        self._callback = callback
        self._last_percentage = -1

    def publish(self, progress: DirectoryCopyProgress) -> None:
        """Publish at most one line for each completed percentage point."""

        percentage = (
            100
            if progress.total_entries == 0
            else int(progress.copied_entries * 100 / progress.total_entries)
        )
        if percentage == self._last_percentage:
            return
        self._last_percentage = percentage
        remaining = (
            "calculating"
            if progress.estimated_remaining_seconds is None
            else _format_duration(progress.estimated_remaining_seconds)
        )
        StandaloneEnvironmentProvisioner._emit(
            self._callback,
            "Copying managed Python packages: "
            f"{progress.copied_entries}/{progress.total_entries} "
            f"({percentage}%), about {remaining} remaining.",
        )


class _ExtractionProgressLog:
    """Translate native extraction progress into user-visible status lines."""

    def __init__(self, callback: ProvisioningLogCallback | None) -> None:
        """Store the output callback and last published percentage."""

        self._callback = callback
        self._last_percentage = -1

    def publish(self, progress: SevenZipExtractionProgress) -> None:
        """Publish each increasing percentage with an approximate ETA."""

        if progress.percentage == self._last_percentage:
            return
        self._last_percentage = progress.percentage
        remaining = (
            "calculating"
            if progress.estimated_remaining_seconds is None
            else _format_duration(progress.estimated_remaining_seconds)
        )
        StandaloneEnvironmentProvisioner._emit(
            self._callback,
            f"Extracting managed environment: {progress.percentage}%, "
            f"about {remaining} remaining.",
        )


def _format_duration(seconds: float) -> str:
    """Return a compact approximate duration for provisioning progress."""

    rounded_seconds = max(0, int(round(seconds)))
    minutes, remaining_seconds = divmod(rounded_seconds, 60)
    if minutes:
        return f"{minutes}m {remaining_seconds:02d}s"
    return f"{remaining_seconds}s"

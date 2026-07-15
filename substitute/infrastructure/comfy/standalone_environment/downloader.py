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

"""Download checksum-addressed standalone environment archive parts."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import requests

from substitute.infrastructure.comfy.standalone_environment.checksum import (
    StandaloneChecksumVerifier,
)
from substitute.infrastructure.comfy.standalone_environment.models import (
    StandaloneArtifact,
    StandaloneArtifactError,
    StandaloneEnvironmentRelease,
)


DownloadProgressCallback = Callable[[int, int], None]


class StandaloneArtifactDownloader:
    """Acquire verified archive parts through bounded streaming requests."""

    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        checksum_verifier: StandaloneChecksumVerifier | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        """Store the HTTP client, checksum owner, and read timeout."""

        self._session = session or requests.Session()
        self._checksum_verifier = checksum_verifier or StandaloneChecksumVerifier()
        self._timeout_seconds = timeout_seconds

    def download(
        self,
        release: StandaloneEnvironmentRelease,
        cache_root: Path,
        *,
        on_progress: DownloadProgressCallback | None = None,
    ) -> tuple[Path, ...]:
        """Download and verify every archive part for one release."""

        release_cache = cache_root / release.release_tag / release.variant.value
        release_cache.mkdir(parents=True, exist_ok=True)
        downloaded: list[Path] = []
        completed_bytes = 0
        for artifact in release.artifacts:
            destination = release_cache / artifact.filename
            if not self._is_verified(
                destination,
                artifact,
                completed_bytes=completed_bytes,
                total_bytes=release.total_size_bytes,
                on_progress=on_progress,
            ):
                destination.unlink(missing_ok=True)
                self._download_artifact(
                    artifact,
                    destination,
                    completed_bytes=completed_bytes,
                    total_bytes=release.total_size_bytes,
                    on_progress=on_progress,
                )
            completed_bytes += artifact.size_bytes
            if on_progress is not None:
                on_progress(completed_bytes, release.total_size_bytes)
            downloaded.append(destination)
        return tuple(downloaded)

    def _download_artifact(
        self,
        artifact: StandaloneArtifact,
        destination: Path,
        *,
        completed_bytes: int,
        total_bytes: int,
        on_progress: DownloadProgressCallback | None,
    ) -> None:
        """Stream one artifact into an atomic partial file and verify it."""

        partial_path = destination.with_name(destination.name + ".part")
        partial_path.unlink(missing_ok=True)
        received = 0
        try:
            with self._session.get(
                artifact.url,
                stream=True,
                timeout=(10.0, self._timeout_seconds),
            ) as response:
                response.raise_for_status()
                with partial_path.open("wb") as file:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        file.write(chunk)
                        received += len(chunk)
                        if on_progress is not None:
                            on_progress(completed_bytes + received, total_bytes)
            self._checksum_verifier.verify(partial_path, artifact)
            partial_path.replace(destination)
        except (OSError, requests.RequestException, StandaloneArtifactError) as error:
            partial_path.unlink(missing_ok=True)
            raise StandaloneArtifactError(
                f"Could not acquire verified artifact {artifact.filename}: {error}"
            ) from error

    def _is_verified(
        self,
        path: Path,
        artifact: StandaloneArtifact,
        *,
        completed_bytes: int,
        total_bytes: int,
        on_progress: DownloadProgressCallback | None,
    ) -> bool:
        """Return whether a cached artifact still matches trusted metadata."""

        try:
            self._checksum_verifier.verify(
                path,
                artifact,
                on_progress=(
                    None
                    if on_progress is None
                    else lambda verified, _artifact_total: on_progress(
                        completed_bytes + verified,
                        total_bytes,
                    )
                ),
            )
        except StandaloneArtifactError:
            return False
        return True

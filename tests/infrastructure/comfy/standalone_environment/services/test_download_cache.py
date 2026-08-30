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

"""Verify standalone artifact download, verification, and cache population."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import cast

import pytest
import requests

from substitute.infrastructure.comfy.standalone_environment.downloader import (
    StandaloneArtifactDownloader,
)
from substitute.infrastructure.comfy.standalone_environment.models import (
    StandaloneArchiveKind,
    StandaloneArtifact,
    StandaloneArtifactError,
    StandaloneEnvironmentRelease,
    StandaloneVariantId,
)
from tools.ci.cache_managed_comfy_artifacts import (
    cache_pinned_managed_comfy_artifacts,
)

from .support import _DownloadSession, _release


def test_downloader_removes_partial_file_after_checksum_failure(tmp_path: Path) -> None:
    """A corrupted download should not remain reusable in the artifact cache."""

    artifact = StandaloneArtifact(
        filename="environment.tar.gz",
        url="https://example.invalid/environment.tar.gz",
        size_bytes=3,
        sha256=hashlib.sha256(b"good").hexdigest(),
    )
    release = _release(artifact, archive_kind=StandaloneArchiveKind.TAR_GZIP)
    session = _DownloadSession(b"bad")

    with pytest.raises(StandaloneArtifactError, match="verified artifact"):
        StandaloneArtifactDownloader(session=cast(requests.Session, session)).download(
            release, tmp_path
        )

    assert not any(tmp_path.rglob("*.part"))
    assert not any(tmp_path.rglob(artifact.filename))


def test_downloader_reports_cached_artifact_verification_progress(
    tmp_path: Path,
) -> None:
    """Cached artifacts should visibly advance while their checksum is verified."""

    content = b"verified-cache"
    artifact = StandaloneArtifact(
        filename="environment.tar.gz",
        url="https://example.invalid/environment.tar.gz",
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
    )
    release = _release(artifact, archive_kind=StandaloneArchiveKind.TAR_GZIP)
    cached_path = (
        tmp_path / release.release_tag / release.variant.value / artifact.filename
    )
    cached_path.parent.mkdir(parents=True)
    cached_path.write_bytes(content)
    progress: list[tuple[int, int]] = []

    downloaded = StandaloneArtifactDownloader().download(
        release,
        tmp_path,
        on_progress=lambda completed, total: progress.append((completed, total)),
    )

    assert downloaded == (cached_path,)
    assert progress[-1] == (len(content), len(content))


def test_ci_cache_populator_acquires_exact_variant_with_bounded_progress(
    tmp_path: Path,
) -> None:
    """Release qualification should populate its external cache before timing install."""

    artifact = StandaloneArtifact(
        filename="environment.tar.gz",
        url="https://example.invalid/environment.tar.gz",
        size_bytes=10,
        sha256="a" * 64,
    )
    release = _release(artifact, archive_kind=StandaloneArchiveKind.TAR_GZIP)
    calls: list[tuple[StandaloneVariantId, Path]] = []

    class _Catalog:
        """Return the one exact release requested by the test."""

        def resolve(self, variant: StandaloneVariantId) -> StandaloneEnvironmentRelease:
            """Record and return the selected standalone variant."""

            calls.append((variant, tmp_path))
            return release

    class _Downloader:
        """Materialize one verified cache artifact without network access."""

        def download(
            self,
            selected_release: StandaloneEnvironmentRelease,
            cache_root: Path,
            *,
            on_progress: object = None,
        ) -> tuple[Path, ...]:
            """Record acquisition and publish deterministic progress."""

            assert selected_release is release
            cached = (
                cache_root
                / release.release_tag
                / release.variant.value
                / artifact.filename
            )
            cached.parent.mkdir(parents=True)
            cached.write_bytes(b"0123456789")
            assert callable(on_progress)
            on_progress(5, 10)
            on_progress(10, 10)
            return (cached,)

    messages: list[str] = []
    artifacts = cache_pinned_managed_comfy_artifacts(
        cache_root=tmp_path,
        variant=StandaloneVariantId.WINDOWS_CPU,
        catalog=_Catalog(),
        downloader=_Downloader(),
        output=messages.append,
    )

    assert calls == [(StandaloneVariantId.WINDOWS_CPU, tmp_path)]
    assert artifacts[0].read_bytes() == b"0123456789"
    assert any("percentage=50" in message for message in messages)
    assert messages[-1].startswith("MANAGED_COMFY_CACHE ready")

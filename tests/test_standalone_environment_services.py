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

"""Test verified standalone environment policy and focused services."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import tarfile
from typing import cast

import py7zr
import pytest
import requests

from substitute.infrastructure.comfy.install_targets import ManagedInstallTarget
from substitute.infrastructure.comfy.standalone_environment.catalog_client import (
    GITHUB_RELEASE_API_TEMPLATE,
    LATEST_CATALOG_URL,
    StandaloneEnvironmentCatalogClient,
)
from substitute.infrastructure.comfy.standalone_environment.downloader import (
    StandaloneArtifactDownloader,
)
from substitute.infrastructure.comfy.standalone_environment.extraction_process import (
    NativeSevenZipExtractionProcess,
    SevenZipExtractionProgress,
    bundled_seven_zip_path,
)
from substitute.infrastructure.comfy.standalone_environment.extractor import (
    StandaloneEnvironmentExtractor,
)
from substitute.infrastructure.comfy.standalone_environment.layout import (
    ManagedStandaloneLayout,
)
from substitute.infrastructure.comfy.standalone_environment.migration import (
    StandaloneWorkspaceMigrator,
)
from substitute.infrastructure.comfy.standalone_environment.models import (
    StandaloneArchiveKind,
    StandaloneArtifact,
    StandaloneArtifactError,
    StandaloneCatalogError,
    StandaloneEnvironmentRelease,
    StandaloneVariantId,
)
from substitute.infrastructure.comfy.standalone_environment.variant_policy import (
    standalone_variant_for_target,
)


class _RecordingSevenZipExtractionProcess:
    """Record delegated extraction and materialize a deterministic marker."""

    def __init__(self) -> None:
        """Initialize an empty call record."""

        self.calls: list[tuple[Path, Path]] = []

    def list_members(self, archive_path: Path) -> tuple[str, ...]:
        """Record no side effect while returning one safe member name."""

        del archive_path
        return ("nested/source.txt",)

    def extract(
        self,
        archive_path: Path,
        destination: Path,
        *,
        on_progress: object = None,
    ) -> None:
        """Record one process-boundary request and simulate extracted output."""

        del on_progress
        self.calls.append((archive_path, destination))
        (destination / "process-boundary.txt").write_text(
            "delegated",
            encoding="utf-8",
        )


def test_variant_policy_matches_current_comfy_desktop_catalog() -> None:
    """Every supported managed target should map to its published catalog ID."""

    assert (
        standalone_variant_for_target(ManagedInstallTarget.WINDOWS_NVIDIA)
        is StandaloneVariantId.WINDOWS_NVIDIA
    )
    assert (
        standalone_variant_for_target(ManagedInstallTarget.LINUX_AMD)
        is StandaloneVariantId.LINUX_AMD
    )
    assert (
        standalone_variant_for_target(ManagedInstallTarget.MACOS_APPLE_SILICON)
        is StandaloneVariantId.MACOS_MPS
    )
    with pytest.raises(ValueError, match="does not publish"):
        standalone_variant_for_target(ManagedInstallTarget.LINUX_CPU)


def test_catalog_joins_live_variant_metadata_to_github_sha256() -> None:
    """Catalog resolution should require GitHub's digest-bearing release asset."""

    content = b"abc"
    filename = "comfyui-standalone-mac-mps-v1-env1.tar.gz"
    tag = "v1-env1"
    session = _CatalogSession(
        {
            LATEST_CATALOG_URL: {
                "mac-mps": {
                    "tag": tag,
                    "file": filename,
                    "size": len(content),
                    "comfyui_version": "v1.0.0",
                    "comfyui_commit": "a" * 40,
                    "python_version": "3.13.12",
                    "torch_version": "2.10.0",
                }
            },
            GITHUB_RELEASE_API_TEMPLATE.format(tag=tag): {
                "assets": [
                    {
                        "name": filename,
                        "size": len(content),
                        "digest": f"sha256:{hashlib.sha256(content).hexdigest()}",
                        "browser_download_url": f"https://example.invalid/{filename}",
                    }
                ]
            },
        }
    )

    release = StandaloneEnvironmentCatalogClient(
        session=cast(requests.Session, session)
    ).resolve(StandaloneVariantId.MACOS_MPS)

    assert release.archive_kind is StandaloneArchiveKind.TAR_GZIP
    assert release.artifacts[0].sha256 == hashlib.sha256(content).hexdigest()
    assert release.python_version == "3.13.12"
    assert release.torch_version == "2.10.0"


def test_catalog_rejects_assets_without_sha256_digest() -> None:
    """Catalog resolution should fail closed when GitHub omits a digest."""

    filename = "comfyui-standalone-win-cpu-v1-env1.7z"
    tag = "v1-env1"
    session = _CatalogSession(
        {
            LATEST_CATALOG_URL: {
                "win-cpu": {
                    "tag": tag,
                    "file": filename,
                    "size": 3,
                    "comfyui_version": "v1.0.0",
                    "comfyui_commit": "a" * 40,
                    "python_version": "3.13.12",
                    "torch_version": "2.10.0+cpu",
                }
            },
            GITHUB_RELEASE_API_TEMPLATE.format(tag=tag): {
                "assets": [
                    {
                        "name": filename,
                        "size": 3,
                        "digest": None,
                        "browser_download_url": "https://example.invalid/file",
                    }
                ]
            },
        }
    )

    with pytest.raises(StandaloneCatalogError, match="SHA256"):
        StandaloneEnvironmentCatalogClient(
            session=cast(requests.Session, session)
        ).resolve(StandaloneVariantId.WINDOWS_CPU)


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


def test_extractor_joins_verified_seven_zip_parts(tmp_path: Path) -> None:
    """Multipart 7z environments should extract directly from the first part."""

    source = tmp_path / "source.txt"
    source.write_text("payload", encoding="utf-8")
    complete_archive = tmp_path / "environment.7z"
    with py7zr.SevenZipFile(complete_archive, mode="w") as archive:
        archive.write(source, "nested/source.txt")
    archive_bytes = complete_archive.read_bytes()
    split_at = len(archive_bytes) // 2
    part_paths = (tmp_path / "environment.7z.001", tmp_path / "environment.7z.002")
    part_paths[0].write_bytes(archive_bytes[:split_at])
    part_paths[1].write_bytes(archive_bytes[split_at:])
    artifacts = tuple(
        StandaloneArtifact(
            filename=path.name,
            url=path.as_uri(),
            size_bytes=path.stat().st_size,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        for path in part_paths
    )
    release = _release(*artifacts, archive_kind=StandaloneArchiveKind.SEVEN_ZIP)
    destination = tmp_path / "extracted"

    StandaloneEnvironmentExtractor().extract(release, part_paths, destination)

    assert (destination / "nested" / "source.txt").read_text(
        encoding="utf-8"
    ) == "payload"
    assert not any(tmp_path.glob("*.combined"))


def test_native_seven_zip_process_reports_progress(tmp_path: Path) -> None:
    """Native extraction should list, extract, and report terminal progress."""

    source = tmp_path / "source.txt"
    source.write_text("payload", encoding="utf-8")
    archive_path = tmp_path / "environment.7z"
    with py7zr.SevenZipFile(archive_path, mode="w") as archive:
        archive.write(source, "nested/source.txt")
    destination = tmp_path / "extracted"
    destination.mkdir()
    progress: list[SevenZipExtractionProgress] = []
    process = NativeSevenZipExtractionProcess()

    assert process.list_members(archive_path) == (str(Path("nested/source.txt")),)
    process.extract(archive_path, destination, on_progress=progress.append)

    assert (destination / "nested" / "source.txt").read_text(
        encoding="utf-8"
    ) == "payload"
    assert progress[-1].percentage == 100


@pytest.mark.parametrize(
    ("platform_name", "machine_name", "expected_relative_path"),
    (
        ("win32", "AMD64", Path("windows-x64/7za.exe")),
        ("linux", "x86_64", Path("linux-x64/7za")),
        ("darwin", "arm64", Path("macos-arm64/7za")),
    ),
)
def test_bundled_seven_zip_path_matches_release_targets(
    tmp_path: Path,
    platform_name: str,
    machine_name: str,
    expected_relative_path: Path,
) -> None:
    """Every release platform should resolve its own bundled native binary."""

    resolved = bundled_seven_zip_path(
        tmp_path,
        platform_name=platform_name,
        machine_name=machine_name,
    )

    assert resolved.relative_to(tmp_path / "third_party" / "bin" / "7zip") == (
        expected_relative_path
    )


def test_extractor_delegates_validated_seven_zip_work_to_process_boundary(
    tmp_path: Path,
) -> None:
    """The parent interpreter should validate names but delegate decompression."""

    source = tmp_path / "source.txt"
    source.write_text("payload", encoding="utf-8")
    archive_path = tmp_path / "environment.7z"
    with py7zr.SevenZipFile(archive_path, mode="w") as archive:
        archive.write(source, "nested/source.txt")
    artifact = StandaloneArtifact(
        filename=archive_path.name,
        url=archive_path.as_uri(),
        size_bytes=archive_path.stat().st_size,
        sha256=hashlib.sha256(archive_path.read_bytes()).hexdigest(),
    )
    process = _RecordingSevenZipExtractionProcess()
    destination = tmp_path / "extracted"

    StandaloneEnvironmentExtractor(seven_zip_process=process).extract(
        _release(artifact, archive_kind=StandaloneArchiveKind.SEVEN_ZIP),
        (archive_path,),
        destination,
    )

    assert process.calls == [(archive_path, destination)]
    assert (destination / "process-boundary.txt").read_text(
        encoding="utf-8"
    ) == "delegated"


def test_tar_extractor_rejects_parent_traversal(tmp_path: Path) -> None:
    """Tar extraction should fail before writing a member outside staging."""

    archive_path = tmp_path / "environment.tar.gz"
    with tarfile.open(archive_path, mode="w:gz") as archive:
        info = tarfile.TarInfo("../escaped.txt")
        payload = b"escape"
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    artifact = StandaloneArtifact(
        filename=archive_path.name,
        url=archive_path.as_uri(),
        size_bytes=archive_path.stat().st_size,
        sha256=hashlib.sha256(archive_path.read_bytes()).hexdigest(),
    )

    with pytest.raises(StandaloneArtifactError, match="unsafe path"):
        StandaloneEnvironmentExtractor().extract(
            _release(artifact, archive_kind=StandaloneArchiveKind.TAR_GZIP),
            (archive_path,),
            tmp_path / "extracted",
        )

    assert not (tmp_path / "escaped.txt").exists()


def test_migrator_promotes_upstream_layout_without_mixing_runtime_roots(
    tmp_path: Path,
) -> None:
    """Promotion should keep master Python separate from the Comfy workspace."""

    extracted = tmp_path / "extracted"
    (extracted / "ComfyUI").mkdir(parents=True)
    (extracted / "ComfyUI" / "main.py").write_text("main", encoding="utf-8")
    (extracted / "standalone-env").mkdir()
    release = _release_for_variant(StandaloneVariantId.WINDOWS_CPU)
    (extracted / "manifest.json").write_text(
        json.dumps({"id": release.variant.value, "version": release.release_tag}),
        encoding="utf-8",
    )
    workspace = tmp_path / "workspace"

    layout = StandaloneWorkspaceMigrator().promote(extracted, workspace, release)

    assert isinstance(layout, ManagedStandaloneLayout)
    assert (workspace / "main.py").is_file()
    assert (workspace / ".standalone-env").is_dir()
    assert layout.manifest.is_file()
    assert not extracted.exists()


class _CatalogResponse:
    """Return one fixed decoded JSON payload."""

    def __init__(self, payload: object) -> None:
        """Store the decoded response payload."""

        self._payload = payload

    def raise_for_status(self) -> None:
        """Represent a successful response."""

    def json(self) -> object:
        """Return the configured decoded payload."""

        return self._payload


class _CatalogSession:
    """Resolve catalog URLs from an in-memory response map."""

    def __init__(self, payloads: dict[str, object]) -> None:
        """Store payloads keyed by requested URL."""

        self._payloads = payloads

    def get(self, url: str, *, timeout: float) -> _CatalogResponse:
        """Return the response registered for one URL."""

        del timeout
        return _CatalogResponse(self._payloads[url])


class _DownloadResponse:
    """Stream one in-memory download response."""

    def __init__(self, content: bytes) -> None:
        """Store response bytes."""

        self._content = content

    def __enter__(self) -> _DownloadResponse:
        """Enter the response context."""

        return self

    def __exit__(self, *args: object) -> None:
        """Exit the response context."""

        del args

    def raise_for_status(self) -> None:
        """Represent a successful download response."""

    def iter_content(self, *, chunk_size: int) -> tuple[bytes, ...]:
        """Return response bytes as one bounded chunk."""

        del chunk_size
        return (self._content,)


class _DownloadSession:
    """Return one fixed streaming response."""

    def __init__(self, content: bytes) -> None:
        """Store response bytes."""

        self._content = content

    def get(
        self,
        url: str,
        *,
        stream: bool,
        timeout: tuple[float, float],
    ) -> _DownloadResponse:
        """Return a successful streaming response."""

        del url, stream, timeout
        return _DownloadResponse(self._content)


def _release(
    *artifacts: StandaloneArtifact,
    archive_kind: StandaloneArchiveKind,
) -> StandaloneEnvironmentRelease:
    """Build one standalone release fixture."""

    return StandaloneEnvironmentRelease(
        variant=StandaloneVariantId.WINDOWS_CPU,
        release_tag="v1-env1",
        comfyui_version="v1.0.0",
        comfyui_commit="a" * 40,
        python_version="3.13.12",
        torch_version="2.10.0+cpu",
        archive_kind=archive_kind,
        artifacts=tuple(artifacts),
    )


def _release_for_variant(
    variant: StandaloneVariantId,
) -> StandaloneEnvironmentRelease:
    """Build a no-download release fixture for layout tests."""

    return StandaloneEnvironmentRelease(
        variant=variant,
        release_tag="v1-env1",
        comfyui_version="v1.0.0",
        comfyui_commit="a" * 40,
        python_version="3.13.12",
        torch_version="2.10.0",
        archive_kind=StandaloneArchiveKind.SEVEN_ZIP,
        artifacts=(),
    )

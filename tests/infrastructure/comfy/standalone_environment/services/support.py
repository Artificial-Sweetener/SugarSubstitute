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

"""Provide deterministic external and extraction boundaries for service tests."""

from __future__ import annotations

from pathlib import Path
from substitute.infrastructure.comfy.standalone_environment.models import (
    StandaloneArchiveKind,
    StandaloneArtifact,
    StandaloneEnvironmentRelease,
    StandaloneVariantId,
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


class _RecordingTarExtractionProcess:
    """Record delegated tar extraction and materialize a deterministic marker."""

    def __init__(self) -> None:
        """Initialize an empty call record."""

        self.calls: list[tuple[Path, Path]] = []

    def extract(self, archive_path: Path, destination: Path) -> None:
        """Record extraction and write one representative extracted file."""

        self.calls.append((archive_path, destination))
        nested = destination / "nested"
        nested.mkdir(parents=True)
        (nested / "payload.txt").write_text("delegated", encoding="utf-8")


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

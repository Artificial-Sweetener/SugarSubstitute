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

"""Verify validated tar extraction and native materialization boundaries."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
import tarfile

import pytest

from substitute.infrastructure.comfy.standalone_environment.extractor import (
    StandaloneEnvironmentExtractor,
)
from substitute.infrastructure.comfy.standalone_environment.models import (
    StandaloneArchiveKind,
    StandaloneArtifact,
    StandaloneArtifactError,
)
from substitute.infrastructure.comfy.standalone_environment.tar_extraction_process import (
    NativeTarExtractionProcess,
)

from .support import _RecordingTarExtractionProcess, _release


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


def test_tar_extractor_rejects_member_nested_under_archive_link(
    tmp_path: Path,
) -> None:
    """Native extraction must not materialize members through archive links."""

    archive_path = tmp_path / "environment.tar.gz"
    with tarfile.open(archive_path, mode="w:gz") as archive:
        link = tarfile.TarInfo("safe/link")
        link.type = tarfile.SYMTYPE
        link.linkname = "../target"
        archive.addfile(link)
        info = tarfile.TarInfo("safe/link/payload.txt")
        payload = b"payload"
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    artifact = StandaloneArtifact(
        filename=archive_path.name,
        url=archive_path.as_uri(),
        size_bytes=archive_path.stat().st_size,
        sha256=hashlib.sha256(archive_path.read_bytes()).hexdigest(),
    )
    process = _RecordingTarExtractionProcess()

    with pytest.raises(StandaloneArtifactError, match="archive link"):
        StandaloneEnvironmentExtractor(tar_process=process).extract(
            _release(artifact, archive_kind=StandaloneArchiveKind.TAR_GZIP),
            (archive_path,),
            tmp_path / "extracted",
        )

    assert process.calls == []


def test_tar_extractor_validates_then_delegates_file_materialization(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Large macOS archives should avoid Python's per-file extraction path."""

    archive_path = tmp_path / "environment.tar.gz"
    with tarfile.open(archive_path, mode="w:gz") as archive:
        info = tarfile.TarInfo("nested/payload.txt")
        payload = b"payload"
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    artifact = StandaloneArtifact(
        filename=archive_path.name,
        url=archive_path.as_uri(),
        size_bytes=archive_path.stat().st_size,
        sha256=hashlib.sha256(archive_path.read_bytes()).hexdigest(),
    )

    def reject_python_extraction(*_args: object, **_kwargs: object) -> None:
        """Fail if materialization remains inside Python's tar implementation."""

        raise AssertionError("Python tar extraction is forbidden")

    monkeypatch.setattr(tarfile.TarFile, "extractall", reject_python_extraction)
    destination = tmp_path / "extracted"
    process = _RecordingTarExtractionProcess()

    StandaloneEnvironmentExtractor(tar_process=process).extract(
        _release(artifact, archive_kind=StandaloneArchiveKind.TAR_GZIP),
        (archive_path,),
        destination,
    )

    assert process.calls == [(archive_path, destination)]
    assert (destination / "nested" / "payload.txt").read_text(
        encoding="utf-8"
    ) == "delegated"


def test_native_tar_process_materializes_validated_archive(tmp_path: Path) -> None:
    """Supported hosts should provide a native tar with the required safe flags."""

    archive_path = tmp_path / "environment.tar.gz"
    with tarfile.open(archive_path, mode="w:gz") as archive:
        info = tarfile.TarInfo("nested/payload.txt")
        payload = b"payload"
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    destination = tmp_path / "extracted"
    destination.mkdir()

    NativeTarExtractionProcess().extract(archive_path, destination)

    assert (destination / "nested" / "payload.txt").read_bytes() == payload

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

"""Verify validated seven-Zip extraction and platform binary resolution."""

from __future__ import annotations

import hashlib
from pathlib import Path

import py7zr
import pytest

from substitute.infrastructure.comfy.standalone_environment.extraction_process import (
    NativeSevenZipExtractionProcess,
    SevenZipExtractionProgress,
    bundled_seven_zip_path,
)
from substitute.infrastructure.comfy.standalone_environment.extractor import (
    StandaloneEnvironmentExtractor,
)
from substitute.infrastructure.comfy.standalone_environment.models import (
    StandaloneArchiveKind,
    StandaloneArtifact,
)

from .support import _RecordingSevenZipExtractionProcess, _release


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

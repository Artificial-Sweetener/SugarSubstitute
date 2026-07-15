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

"""Securely extract verified standalone environment archives."""

from __future__ import annotations

import shutil
import tarfile
from pathlib import Path, PurePosixPath

from substitute.infrastructure.comfy.standalone_environment.extraction_process import (
    NativeSevenZipExtractionProcess,
    SevenZipExtractionProcess,
    SevenZipProgressCallback,
)
from substitute.infrastructure.comfy.standalone_environment.models import (
    StandaloneArchiveKind,
    StandaloneArtifactError,
    StandaloneEnvironmentRelease,
)


class StandaloneEnvironmentExtractor:
    """Extract supported archives into a new staging directory fail closed."""

    def __init__(
        self,
        *,
        seven_zip_process: SevenZipExtractionProcess | None = None,
    ) -> None:
        """Store the process boundary used for CPU-bound 7z decompression."""

        self._seven_zip_process = seven_zip_process or NativeSevenZipExtractionProcess()

    def extract(
        self,
        release: StandaloneEnvironmentRelease,
        artifact_paths: tuple[Path, ...],
        destination: Path,
        *,
        on_extraction_progress: SevenZipProgressCallback | None = None,
    ) -> Path:
        """Extract one complete verified release into an empty destination."""

        self._validate_inputs(release, artifact_paths, destination)
        destination.mkdir(parents=True)
        try:
            if release.archive_kind is StandaloneArchiveKind.TAR_GZIP:
                self._extract_tar(artifact_paths[0], destination)
            else:
                self._extract_seven_zip(
                    artifact_paths,
                    destination,
                    on_progress=on_extraction_progress,
                )
        except (
            OSError,
            tarfile.TarError,
            StandaloneArtifactError,
        ) as error:
            shutil.rmtree(destination, ignore_errors=True)
            raise StandaloneArtifactError(
                f"Could not extract {release.variant.value}: {error}"
            ) from error
        return destination

    def _extract_tar(self, archive_path: Path, destination: Path) -> None:
        """Extract a gzip-compressed tar after validating every member path."""

        with tarfile.open(archive_path, mode="r:gz") as archive:
            for member in archive.getmembers():
                _validate_member_path(member.name)
                if member.isdev() or member.isfifo():
                    raise StandaloneArtifactError(
                        f"Standalone tar contains a special file: {member.name}"
                    )
                if member.issym() or member.islnk():
                    _validate_link_target(member.name, member.linkname)
            archive.extractall(destination, filter="data")

    def _extract_seven_zip(
        self,
        artifact_paths: tuple[Path, ...],
        destination: Path,
        *,
        on_progress: SevenZipProgressCallback | None,
    ) -> None:
        """Validate and extract from the first native multipart archive path."""

        archive_path = artifact_paths[0]
        for filename in self._seven_zip_process.list_members(archive_path):
            _validate_member_path(filename)
        self._seven_zip_process.extract(
            archive_path,
            destination,
            on_progress=on_progress,
        )

    def _validate_inputs(
        self,
        release: StandaloneEnvironmentRelease,
        artifact_paths: tuple[Path, ...],
        destination: Path,
    ) -> None:
        """Require ordered complete artifacts and a new staging destination."""

        if destination.exists():
            raise StandaloneArtifactError(
                f"Standalone extraction destination already exists: {destination}"
            )
        expected_names = tuple(artifact.filename for artifact in release.artifacts)
        actual_names = tuple(path.name for path in artifact_paths)
        if actual_names != expected_names:
            raise StandaloneArtifactError(
                f"Standalone archive parts do not match release metadata: {actual_names}"
            )
        if any(not path.is_file() for path in artifact_paths):
            raise StandaloneArtifactError("A standalone archive part is missing.")


def _validate_member_path(member_name: str) -> None:
    """Reject absolute and parent-traversing archive member paths."""

    normalized = member_name.replace("\\", "/")
    member_path = PurePosixPath(normalized)
    if member_path.is_absolute() or ".." in member_path.parts:
        raise StandaloneArtifactError(
            f"Standalone archive contains an unsafe path: {member_name}"
        )
    if member_path.parts and ":" in member_path.parts[0]:
        raise StandaloneArtifactError(
            f"Standalone archive contains a drive-qualified path: {member_name}"
        )


def _validate_link_target(member_name: str, link_name: str) -> None:
    """Reject archive links whose lexical target escapes the extraction root."""

    normalized_target = link_name.replace("\\", "/")
    target = PurePosixPath(normalized_target)
    if target.is_absolute():
        raise StandaloneArtifactError(
            f"Standalone archive link is absolute: {member_name}"
        )
    combined = PurePosixPath(member_name).parent / target
    depth = 0
    for part in combined.parts:
        depth = depth - 1 if part == ".." else depth + (part not in {"", "."})
        if depth < 0:
            raise StandaloneArtifactError(
                f"Standalone archive link escapes its root: {member_name}"
            )

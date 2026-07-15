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

"""Verify standalone environment artifacts before extraction."""

from __future__ import annotations

from collections.abc import Callable
import hashlib
from pathlib import Path

from substitute.infrastructure.comfy.standalone_environment.models import (
    StandaloneArtifact,
    StandaloneArtifactError,
)


ChecksumProgressCallback = Callable[[int, int], None]


class StandaloneChecksumVerifier:
    """Enforce the GitHub-published size and SHA256 for one artifact."""

    def verify(
        self,
        path: Path,
        artifact: StandaloneArtifact,
        *,
        on_progress: ChecksumProgressCallback | None = None,
    ) -> None:
        """Raise when one artifact differs from its trusted metadata."""

        if not path.is_file():
            raise StandaloneArtifactError(f"Standalone artifact is missing: {path}")
        actual_size = path.stat().st_size
        if actual_size != artifact.size_bytes:
            raise StandaloneArtifactError(
                f"Standalone artifact size mismatch for {artifact.filename}: "
                f"expected {artifact.size_bytes}, received {actual_size}."
            )
        digest = hashlib.sha256()
        verified_bytes = 0
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
                verified_bytes += len(chunk)
                if on_progress is not None:
                    on_progress(verified_bytes, artifact.size_bytes)
        actual_sha256 = digest.hexdigest()
        if actual_sha256 != artifact.sha256:
            raise StandaloneArtifactError(
                f"Standalone artifact checksum mismatch for {artifact.filename}."
            )

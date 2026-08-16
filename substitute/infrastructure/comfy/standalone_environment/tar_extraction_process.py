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

"""Materialize validated tar archives through the platform-native extractor."""

from __future__ import annotations

import logging
from pathlib import Path
import shutil
import subprocess
import time
from typing import Protocol

from substitute.infrastructure.comfy.standalone_environment.models import (
    StandaloneArtifactError,
)
from sugarsubstitute_shared.windows_long_paths import (
    subprocess_path,
    subprocess_working_directory,
)


_LOGGER = logging.getLogger(__name__)
_DEFAULT_EXTRACTION_TIMEOUT_SECONDS = 7_200.0
_OUTPUT_TAIL_LIMIT = 2_000


class TarExtractionProcess(Protocol):
    """Materialize one already-validated gzip-compressed tar archive."""

    def extract(self, archive_path: Path, destination: Path) -> None:
        """Extract the archive into the existing destination directory."""


class NativeTarExtractionProcess:
    """Use the operating system's native tar implementation for file writes."""

    def __init__(
        self,
        *,
        executable_path: Path | None = None,
        timeout_seconds: float = _DEFAULT_EXTRACTION_TIMEOUT_SECONDS,
    ) -> None:
        """Store an optional executable override and bounded extraction timeout."""

        if timeout_seconds <= 0:
            raise ValueError("Extraction timeout must be positive.")
        self._executable_path = executable_path
        self._timeout_seconds = timeout_seconds

    def extract(self, archive_path: Path, destination: Path) -> None:
        """Materialize validated members without Python per-file overhead."""

        executable = self._resolve_executable()
        command = (
            subprocess_path(executable),
            "--no-same-owner",
            "--no-same-permissions",
            "-xzf",
            subprocess_path(archive_path),
            "-C",
            subprocess_path(destination),
        )
        started_at = time.monotonic()
        _LOGGER.info(
            "Starting native standalone tar extraction | archive_name=%s",
            archive_path.name,
        )
        try:
            completed = subprocess.run(  # noqa: S603
                command,
                cwd=subprocess_working_directory(archive_path.parent),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self._timeout_seconds,
                check=False,
                shell=False,
            )
        except subprocess.TimeoutExpired as error:
            raise StandaloneArtifactError(
                "Native standalone tar extraction timed out."
            ) from error
        except OSError as error:
            raise StandaloneArtifactError(
                "Could not start the native tar extraction process."
            ) from error
        if completed.returncode != 0:
            detail = _tail_output(completed.stdout)
            _LOGGER.error(
                "Native standalone tar extraction failed | archive_name=%s "
                "return_code=%d output=%s",
                archive_path.name,
                completed.returncode,
                detail,
            )
            suffix = f" Details: {detail}" if detail else ""
            raise StandaloneArtifactError(
                "Native tar extraction failed with exit code "
                f"{completed.returncode}.{suffix}"
            )
        _LOGGER.info(
            "Native standalone tar extraction completed | archive_name=%s "
            "elapsed_seconds=%.3f",
            archive_path.name,
            time.monotonic() - started_at,
        )

    def _resolve_executable(self) -> Path:
        """Resolve an explicit or PATH-provided native tar executable."""

        if self._executable_path is not None:
            executable = self._executable_path
        else:
            resolved = shutil.which("tar")
            if resolved is None:
                raise StandaloneArtifactError(
                    "The platform-native tar executable is unavailable."
                )
            executable = Path(resolved)
        if not executable.is_file():
            raise StandaloneArtifactError(
                f"The platform-native tar executable is missing: {executable}"
            )
        return executable.resolve()


def _tail_output(output: str | None) -> str:
    """Return bounded single-line native-process diagnostics."""

    if not output:
        return ""
    return " ".join(output.split())[-_OUTPUT_TAIL_LIMIT:]


__all__ = ["NativeTarExtractionProcess", "TarExtractionProcess"]

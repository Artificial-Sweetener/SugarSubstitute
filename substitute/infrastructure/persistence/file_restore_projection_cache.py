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

"""Persist restore projection cache artifacts as atomic JSON files."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from substitute.application.workspace_state import (
    RestoreProjectionArtifact,
    RestoreProjectionCacheRepository,
    restore_projection_artifact_from_json,
    restore_projection_artifact_to_json,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.persistence.file_restore_projection_cache")
_CACHE_FILE_NAME = "restore-projection-cache.json"


class FileRestoreProjectionCacheRepository(RestoreProjectionCacheRepository):
    """Load, save, and clear the last-known-good restore projection cache."""

    def __init__(self, cache_dir: Path) -> None:
        """Create a repository rooted at the Substitute app cache directory."""

        self._cache_dir = Path(cache_dir)
        self._path = self._cache_dir / _CACHE_FILE_NAME
        self._temp_path = self._cache_dir / f"{_CACHE_FILE_NAME}.tmp"

    @property
    def path(self) -> Path:
        """Return the durable cache artifact path for diagnostics and tests."""

        return self._path

    def load(self) -> RestoreProjectionArtifact | None:
        """Return the latest restore projection artifact when it is readable."""

        if not self._path.exists():
            return None
        try:
            decoded = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(decoded, Mapping):
                raise ValueError("Restore projection cache root must be an object.")
            artifact = restore_projection_artifact_from_json(decoded)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            log_warning(
                _LOGGER,
                "Failed to load restore projection cache",
                cache_path=str(self._path),
                error=repr(error),
            )
            return None
        return artifact

    def save(self, artifact: RestoreProjectionArtifact) -> None:
        """Persist one restore projection artifact through atomic replacement."""

        serialized = (
            json.dumps(
                restore_projection_artifact_to_json(artifact),
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._temp_path.write_text(serialized, encoding="utf-8")
        self._temp_path.replace(self._path)

    def clear(self) -> None:
        """Remove the restore projection cache file when present."""

        try:
            self._path.unlink()
        except FileNotFoundError:
            return


__all__ = ["FileRestoreProjectionCacheRepository"]

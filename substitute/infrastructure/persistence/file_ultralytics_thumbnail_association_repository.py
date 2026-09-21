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

"""Persist user-selected Ultralytics thumbnail associations as JSON."""

from __future__ import annotations

from collections.abc import Mapping
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.persistence.ultralytics_thumbnail_associations")
_SCHEMA_VERSION = 1
_FILE_NAME = "ultralytics-thumbnail-associations.json"


class FileUltralyticsThumbnailAssociationRepository:
    """Store authoritative thumbnail choices under the user settings directory."""

    def __init__(self, settings_dir: Path) -> None:
        """Store the active installation settings directory."""

        self._settings_dir = settings_dir

    def load(self) -> Mapping[str, str]:
        """Load associations or return an empty mapping when absent or invalid."""

        path = self._path()
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            log_warning(
                _LOGGER,
                "Failed to load Ultralytics thumbnail associations",
                path=path,
                error=repr(error),
            )
            return {}
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != _SCHEMA_VERSION
        ):
            return {}
        raw_associations = payload.get("associations")
        if not isinstance(raw_associations, dict):
            return {}
        return {
            backend_value: asset_name
            for backend_value, asset_name in raw_associations.items()
            if isinstance(backend_value, str) and isinstance(asset_name, str)
        }

    def save(self, associations: Mapping[str, str]) -> None:
        """Persist the complete mapping through a same-directory atomic replace."""

        path = self._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": _SCHEMA_VERSION,
            "associations": dict(sorted(associations.items())),
        }
        temporary_name: str | None = None
        try:
            with NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                json.dump(payload, temporary, indent=2, ensure_ascii=False)
                temporary.write("\n")
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_name = temporary.name
            os.replace(temporary_name, path)
        finally:
            if temporary_name is not None:
                temporary_path = Path(temporary_name)
                if temporary_path.exists():
                    temporary_path.unlink()

    def _path(self) -> Path:
        """Return the authoritative preference file path."""

        return self._settings_dir / _FILE_NAME


__all__ = ["FileUltralyticsThumbnailAssociationRepository"]

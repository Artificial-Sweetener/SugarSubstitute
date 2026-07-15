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

"""Persist non-secret CivitAI preferences as JSON."""

from __future__ import annotations

import json
from pathlib import Path

from substitute.application.ports.civitai_preference_repository import (
    CivitaiPreferenceRepository,
)
from substitute.domain.civitai import (
    CIVITAI_PREFERENCES_SCHEMA_VERSION,
    DEFAULT_CIVITAI_DOWNLOAD_PATH_PATTERN,
    CivitaiPreferences,
    CivitaiThumbnailSafetyPolicy,
    default_civitai_preferences,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.persistence.civitai_preferences")
_PREFERENCES_FILE_NAME = "civitai.json"


class FileCivitaiPreferenceRepository(CivitaiPreferenceRepository):
    """Load and save CivitAI preferences from `config/civitai.json`."""

    def __init__(self, settings_dir: Path) -> None:
        """Store the active installation settings directory."""

        self._settings_dir = settings_dir

    def load(self) -> CivitaiPreferences:
        """Load CivitAI preferences or return defaults when absent or invalid."""

        path = self._path()
        if not path.exists():
            return default_civitai_preferences()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            log_warning(
                _LOGGER,
                "Failed to load CivitAI preferences; using defaults.",
                path=path,
                error=repr(error),
            )
            return default_civitai_preferences()
        if not isinstance(payload, dict):
            return default_civitai_preferences()

        raw_policy = payload.get(
            "thumbnail_safety_policy",
            CivitaiThumbnailSafetyPolicy.SFW_ONLY.value,
        )
        try:
            thumbnail_policy = CivitaiThumbnailSafetyPolicy(str(raw_policy))
        except ValueError:
            thumbnail_policy = CivitaiThumbnailSafetyPolicy.SFW_ONLY
        return CivitaiPreferences(
            schema_version=str(
                payload.get("schema_version", CIVITAI_PREFERENCES_SCHEMA_VERSION)
            ),
            metadata_lookup_enabled=bool(payload.get("metadata_lookup_enabled", True)),
            missing_model_lookup_enabled=bool(
                payload.get("missing_model_lookup_enabled", True)
            ),
            thumbnail_downloads_enabled=bool(
                payload.get("thumbnail_downloads_enabled", True)
            ),
            thumbnail_safety_policy=thumbnail_policy,
            downloads_enabled=bool(payload.get("downloads_enabled", True)),
            download_path_pattern=str(
                payload.get(
                    "download_path_pattern",
                    DEFAULT_CIVITAI_DOWNLOAD_PATH_PATTERN,
                )
            ),
        )

    def save(self, preferences: CivitaiPreferences) -> None:
        """Persist CivitAI preferences with stable JSON formatting."""

        path = self._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": CIVITAI_PREFERENCES_SCHEMA_VERSION,
            "metadata_lookup_enabled": preferences.metadata_lookup_enabled,
            "missing_model_lookup_enabled": preferences.missing_model_lookup_enabled,
            "thumbnail_downloads_enabled": preferences.thumbnail_downloads_enabled,
            "thumbnail_safety_policy": preferences.thumbnail_safety_policy.value,
            "downloads_enabled": preferences.downloads_enabled,
            "download_path_pattern": preferences.download_path_pattern,
        }
        path.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")

    def _path(self) -> Path:
        """Return the CivitAI preference file path."""

        return self._settings_dir / _PREFERENCES_FILE_NAME


__all__ = ["FileCivitaiPreferenceRepository"]

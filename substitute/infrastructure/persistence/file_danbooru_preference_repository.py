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

"""Persist Danbooru preferences as JSON under the installation config root."""

from __future__ import annotations

import json
from pathlib import Path

from substitute.application.ports.danbooru_preference_repository import (
    DanbooruPreferenceRepository,
)
from substitute.domain.danbooru.preferences import (
    DANBOORU_PREFERENCES_SCHEMA_VERSION,
    DanbooruImageRatingPolicy,
    DanbooruPreferences,
    default_danbooru_preferences,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.persistence.danbooru_preferences")
_PREFERENCES_FILE_NAME = "danbooru.json"


class FileDanbooruPreferenceRepository(DanbooruPreferenceRepository):
    """Load and save Danbooru preferences from `config/danbooru.json`."""

    def __init__(self, settings_dir: Path) -> None:
        """Store the active installation config directory."""

        self._settings_dir = settings_dir

    def load(self) -> DanbooruPreferences:
        """Load Danbooru preferences or return defaults when absent or invalid."""

        path = self._path()
        if not path.exists():
            return default_danbooru_preferences()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            log_warning(
                _LOGGER,
                "Failed to load Danbooru preferences; using defaults.",
                path=path,
                error=repr(error),
            )
            return default_danbooru_preferences()
        if not isinstance(payload, dict):
            return default_danbooru_preferences()

        raw_policy = payload.get(
            "allowed_image_ratings",
            DanbooruImageRatingPolicy.SAFE_ONLY.value,
        )
        try:
            policy = (
                raw_policy
                if isinstance(raw_policy, DanbooruImageRatingPolicy)
                else DanbooruImageRatingPolicy(str(raw_policy))
            )
        except ValueError:
            policy = DanbooruImageRatingPolicy.SAFE_ONLY

        return DanbooruPreferences(
            schema_version=str(
                payload.get("schema_version", DANBOORU_PREFERENCES_SCHEMA_VERSION)
            ),
            show_wiki_images=bool(payload.get("show_wiki_images", True)),
            allowed_image_ratings=policy,
            background_refresh_enabled=bool(
                payload.get("background_refresh_enabled", True)
            ),
        )

    def save(self, preferences: DanbooruPreferences) -> None:
        """Persist Danbooru preferences with stable JSON formatting."""

        path = self._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": DANBOORU_PREFERENCES_SCHEMA_VERSION,
            "show_wiki_images": preferences.show_wiki_images,
            "allowed_image_ratings": preferences.allowed_image_ratings.value,
            "background_refresh_enabled": preferences.background_refresh_enabled,
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _path(self) -> Path:
        """Return the Danbooru preference file path."""

        return self._settings_dir / _PREFERENCES_FILE_NAME


__all__ = ["FileDanbooruPreferenceRepository"]

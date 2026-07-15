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

"""Coordinate Danbooru preference loading, saving, and policy checks."""

from __future__ import annotations

from substitute.application.ports.danbooru_preference_repository import (
    DanbooruPreferenceRepository,
)
from substitute.domain.danbooru.preferences import (
    DANBOORU_PREFERENCES_SCHEMA_VERSION,
    DanbooruImageRatingPolicy,
    DanbooruPreferences,
    default_danbooru_preferences,
)


class DanbooruPreferenceService:
    """Own Danbooru viewer preference use cases."""

    def __init__(self, repository: DanbooruPreferenceRepository) -> None:
        """Store the Danbooru preference repository."""

        self._repository = repository

    def load_preferences(self) -> DanbooruPreferences:
        """Load normalized Danbooru preferences."""

        return self._normalize(self._repository.load())

    def default_preferences(self) -> DanbooruPreferences:
        """Return default Danbooru preferences."""

        return default_danbooru_preferences()

    def save_preferences(self, preferences: DanbooruPreferences) -> DanbooruPreferences:
        """Persist one normalized Danbooru preference snapshot."""

        normalized = self._normalize(preferences)
        self._repository.save(normalized)
        return normalized

    def set_show_wiki_images(self, enabled: bool) -> DanbooruPreferences:
        """Persist whether the wiki viewer may render preview images."""

        return self.save_preferences(
            self.load_preferences().with_show_wiki_images(enabled)
        )

    def set_allowed_image_ratings(
        self,
        policy: DanbooruImageRatingPolicy,
    ) -> DanbooruPreferences:
        """Persist the allowed Danbooru image rating policy."""

        return self.save_preferences(
            self.load_preferences().with_allowed_image_ratings(policy)
        )

    def set_background_refresh_enabled(self, enabled: bool) -> DanbooruPreferences:
        """Persist whether stale cached entities refresh in the background."""

        return self.save_preferences(
            self.load_preferences().with_background_refresh_enabled(enabled)
        )

    def image_rating_is_allowed(self, rating: str | None) -> bool:
        """Return whether one Danbooru rating may be rendered in-app."""

        preferences = self.load_preferences()
        if not preferences.show_wiki_images:
            return False
        normalized_rating = (rating or "").strip().lower()
        if preferences.allowed_image_ratings is DanbooruImageRatingPolicy.ALL_RATINGS:
            return normalized_rating in {"g", "s", "q", "e"}
        if (
            preferences.allowed_image_ratings
            is DanbooruImageRatingPolicy.SAFE_AND_QUESTIONABLE
        ):
            return normalized_rating in {"g", "s", "q"}
        return normalized_rating in {"g", "s"}

    @staticmethod
    def _normalize(preferences: DanbooruPreferences) -> DanbooruPreferences:
        """Return preferences with the current schema version."""

        return DanbooruPreferences(
            schema_version=DANBOORU_PREFERENCES_SCHEMA_VERSION,
            show_wiki_images=preferences.show_wiki_images,
            allowed_image_ratings=preferences.allowed_image_ratings,
            background_refresh_enabled=preferences.background_refresh_enabled,
        )


__all__ = ["DanbooruPreferenceService"]

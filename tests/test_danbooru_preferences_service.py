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

"""Unit tests for Danbooru preference persistence and policy resolution."""

from __future__ import annotations

from pathlib import Path

from substitute.application.danbooru.preferences_service import (
    DanbooruPreferenceService,
)
from substitute.domain.danbooru.preferences import (
    DanbooruImageRatingPolicy,
    DanbooruPreferences,
    default_danbooru_preferences,
)
from substitute.infrastructure.persistence.file_danbooru_preference_repository import (
    FileDanbooruPreferenceRepository,
)


class _MemoryDanbooruPreferenceRepository:
    """Persist Danbooru preferences in memory for unit tests."""

    def __init__(self) -> None:
        """Initialize the repository with default Danbooru preferences."""

        self.preferences = default_danbooru_preferences()

    def load(self) -> DanbooruPreferences:
        """Return the current preference snapshot."""

        return self.preferences

    def save(self, preferences: DanbooruPreferences) -> None:
        """Persist one preference snapshot in memory."""

        self.preferences = preferences


def test_danbooru_preference_service_applies_rating_policy() -> None:
    """Danbooru image policy should track visibility and allowed ratings."""

    service = DanbooruPreferenceService(_MemoryDanbooruPreferenceRepository())

    assert service.image_rating_is_allowed("s") is True
    assert service.image_rating_is_allowed("q") is False

    service.set_allowed_image_ratings(DanbooruImageRatingPolicy.SAFE_AND_QUESTIONABLE)
    assert service.image_rating_is_allowed("q") is True
    assert service.image_rating_is_allowed("e") is False

    service.set_allowed_image_ratings(DanbooruImageRatingPolicy.ALL_RATINGS)
    assert service.image_rating_is_allowed("e") is True

    service.set_show_wiki_images(False)
    assert service.image_rating_is_allowed("s") is False


def test_file_danbooru_preference_repository_round_trips_preferences(
    tmp_path: Path,
) -> None:
    """Danbooru preferences should persist to the config-root JSON file."""

    repository = FileDanbooruPreferenceRepository(tmp_path)
    saved = DanbooruPreferences(
        schema_version="1",
        show_wiki_images=False,
        allowed_image_ratings=DanbooruImageRatingPolicy.ALL_RATINGS,
        background_refresh_enabled=False,
    )

    repository.save(saved)
    loaded = repository.load()

    assert loaded == saved

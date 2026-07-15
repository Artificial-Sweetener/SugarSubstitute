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

"""Define persisted Danbooru viewer and cache preferences."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

DANBOORU_PREFERENCES_SCHEMA_VERSION = "1"


class DanbooruImageRatingPolicy(str, Enum):
    """Identify which Danbooru image ratings may be rendered in-app."""

    SAFE_ONLY = "safe_only"
    SAFE_AND_QUESTIONABLE = "safe_and_questionable"
    ALL_RATINGS = "all_ratings"


@dataclass(frozen=True, slots=True)
class DanbooruPreferences:
    """Capture Danbooru-specific wiki viewer and cache preferences."""

    schema_version: str
    show_wiki_images: bool
    allowed_image_ratings: DanbooruImageRatingPolicy
    background_refresh_enabled: bool

    def with_show_wiki_images(self, enabled: bool) -> DanbooruPreferences:
        """Return one copy with image visibility updated."""

        return DanbooruPreferences(
            schema_version=self.schema_version,
            show_wiki_images=enabled,
            allowed_image_ratings=self.allowed_image_ratings,
            background_refresh_enabled=self.background_refresh_enabled,
        )

    def with_allowed_image_ratings(
        self,
        policy: DanbooruImageRatingPolicy,
    ) -> DanbooruPreferences:
        """Return one copy with the allowed image rating policy updated."""

        return DanbooruPreferences(
            schema_version=self.schema_version,
            show_wiki_images=self.show_wiki_images,
            allowed_image_ratings=policy,
            background_refresh_enabled=self.background_refresh_enabled,
        )

    def with_background_refresh_enabled(
        self,
        enabled: bool,
    ) -> DanbooruPreferences:
        """Return one copy with background refresh enablement updated."""

        return DanbooruPreferences(
            schema_version=self.schema_version,
            show_wiki_images=self.show_wiki_images,
            allowed_image_ratings=self.allowed_image_ratings,
            background_refresh_enabled=enabled,
        )


def default_danbooru_preferences() -> DanbooruPreferences:
    """Return the default Danbooru settings snapshot."""

    return DanbooruPreferences(
        schema_version=DANBOORU_PREFERENCES_SCHEMA_VERSION,
        show_wiki_images=True,
        allowed_image_ratings=DanbooruImageRatingPolicy.SAFE_ONLY,
        background_refresh_enabled=True,
    )


__all__ = [
    "DANBOORU_PREFERENCES_SCHEMA_VERSION",
    "DanbooruImageRatingPolicy",
    "DanbooruPreferences",
    "default_danbooru_preferences",
]

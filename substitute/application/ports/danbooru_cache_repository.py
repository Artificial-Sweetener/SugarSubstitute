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

"""Define persistence contract for cached Danbooru metadata and preview assets."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from substitute.domain.danbooru import (
    DanbooruCacheSummary,
    DanbooruCachedImageAsset,
    DanbooruCachedPost,
    DanbooruCachedPostSearch,
    DanbooruCachedTag,
    DanbooruCachedWikiPage,
)


@runtime_checkable
class DanbooruCacheRepository(Protocol):
    """Persist cached Danbooru records and preview image assets."""

    def load_cached_wiki_page(self, title: str) -> DanbooruCachedWikiPage | None:
        """Return one cached wiki page entry by title when present."""

    def save_cached_wiki_page(self, entry: DanbooruCachedWikiPage) -> None:
        """Persist one cached wiki page entry."""

    def list_cached_wiki_pages(self) -> tuple[DanbooruCachedWikiPage, ...]:
        """Return all cached wiki page entries in deterministic title order."""

    def load_cached_tag(self, name: str) -> DanbooruCachedTag | None:
        """Return one cached tag entry by exact name when present."""

    def save_cached_tag(self, entry: DanbooruCachedTag) -> None:
        """Persist one cached tag entry."""

    def load_cached_post(self, post_id: int) -> DanbooruCachedPost | None:
        """Return one cached post entry by post identifier when present."""

    def save_cached_post(self, entry: DanbooruCachedPost) -> None:
        """Persist one cached post entry."""

    def load_cached_post_search(self, tag_name: str) -> DanbooruCachedPostSearch | None:
        """Return one cached tag-post search entry when present."""

    def save_cached_post_search(self, entry: DanbooruCachedPostSearch) -> None:
        """Persist one cached tag-post search entry."""

    def load_cached_image_asset(
        self, cache_key: str
    ) -> DanbooruCachedImageAsset | None:
        """Return one cached preview image asset when present."""

    def save_cached_image_asset(
        self,
        asset: DanbooruCachedImageAsset,
        image_bytes: bytes,
    ) -> DanbooruCachedImageAsset:
        """Persist one cached preview image asset and return the stored record."""

    def touch_cached_image_asset(self, cache_key: str, *, last_used_at: str) -> None:
        """Update one cached image asset's last-used timestamp when present."""

    def clear_text_cache(self) -> None:
        """Delete cached wiki, tag, and post metadata."""

    def clear_image_cache(self) -> None:
        """Delete cached preview image files and their metadata rows."""

    def clear_all_cache(self) -> None:
        """Delete all cached Danbooru metadata and preview assets."""

    def cache_summary(self) -> DanbooruCacheSummary:
        """Return the current cache entry counts and image byte usage."""


__all__ = ["DanbooruCacheRepository"]

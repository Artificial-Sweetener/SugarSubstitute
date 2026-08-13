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

"""Compose independently governed Danbooru metadata and image cache stores."""

from __future__ import annotations

from substitute.domain.danbooru import (
    DanbooruCacheSummary,
    DanbooruCachedImageAsset,
    DanbooruCachedPost,
    DanbooruCachedPostSearch,
    DanbooruCachedTag,
    DanbooruCachedWikiPage,
)
from substitute.infrastructure.persistence.danbooru_cache_store import (
    SqliteDanbooruMetadataStore,
)
from substitute.infrastructure.persistence.danbooru_image_cache_store import (
    SqliteDanbooruImageCacheStore,
)


class ComposedDanbooruCacheRepository:
    """Present one application port while preserving separate storage ownership."""

    def __init__(
        self,
        metadata: SqliteDanbooruMetadataStore,
        images: SqliteDanbooruImageCacheStore,
    ) -> None:
        """Store cohesive metadata and image collaborators."""

        self._metadata = metadata
        self._images = images

    def load_cached_wiki_page(self, title: str) -> DanbooruCachedWikiPage | None:
        """Return one cached wiki page entry by title when present."""

        return self._metadata.load_cached_wiki_page(title)

    def save_cached_wiki_page(self, entry: DanbooruCachedWikiPage) -> None:
        """Persist one cached wiki page entry."""

        self._metadata.save_cached_wiki_page(entry)

    def list_cached_wiki_pages(self) -> tuple[DanbooruCachedWikiPage, ...]:
        """Return all cached wiki pages in deterministic title order."""

        return self._metadata.list_cached_wiki_pages()

    def load_cached_tag(self, name: str) -> DanbooruCachedTag | None:
        """Return one cached tag entry by exact name when present."""

        return self._metadata.load_cached_tag(name)

    def save_cached_tag(self, entry: DanbooruCachedTag) -> None:
        """Persist one cached tag entry."""

        self._metadata.save_cached_tag(entry)

    def load_cached_post(self, post_id: int) -> DanbooruCachedPost | None:
        """Return one cached post entry by post identifier when present."""

        return self._metadata.load_cached_post(post_id)

    def save_cached_post(self, entry: DanbooruCachedPost) -> None:
        """Persist one cached post entry."""

        self._metadata.save_cached_post(entry)

    def load_cached_post_search(self, tag_name: str) -> DanbooruCachedPostSearch | None:
        """Return one cached tag-post search entry when present."""

        return self._metadata.load_cached_post_search(tag_name)

    def save_cached_post_search(self, entry: DanbooruCachedPostSearch) -> None:
        """Persist one cached tag-post search entry."""

        self._metadata.save_cached_post_search(entry)

    def load_cached_image_asset(
        self,
        cache_key: str,
    ) -> DanbooruCachedImageAsset | None:
        """Return one cached preview image asset when present."""

        return self._images.load_cached_image_asset(cache_key)

    def save_cached_image_asset(
        self,
        asset: DanbooruCachedImageAsset,
        image_bytes: bytes,
    ) -> DanbooruCachedImageAsset:
        """Persist one cached preview image asset and return its stored record."""

        return self._images.save_cached_image_asset(asset, image_bytes)

    def touch_cached_image_asset(self, cache_key: str, *, last_used_at: str) -> None:
        """Update one cached image asset's last-used timestamp when present."""

        self._images.touch_cached_image_asset(cache_key, last_used_at=last_used_at)

    def clear_text_cache(self) -> None:
        """Delete cached wiki, tag, post, and search metadata."""

        self._metadata.clear_text_cache()

    def clear_image_cache(self) -> None:
        """Delete cached preview image files and records."""

        self._images.clear()

    def clear_all_cache(self) -> None:
        """Delete all cached Danbooru metadata and preview assets."""

        self.clear_text_cache()
        self.clear_image_cache()

    def cache_summary(self) -> DanbooruCacheSummary:
        """Return combined metadata and image cache usage."""

        image_count, image_bytes = self._images.summary()
        return DanbooruCacheSummary(
            metadata_entry_count=self._metadata.entry_count(),
            image_entry_count=image_count,
            image_bytes=image_bytes,
        )


__all__ = ["ComposedDanbooruCacheRepository"]

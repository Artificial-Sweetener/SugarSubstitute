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

"""Load bounded recent Danbooru posts for wiki-page supplemental galleries."""

from __future__ import annotations

from typing import Protocol

from substitute.application.danbooru.cache_policy import (
    POST_CACHE_TTL,
    RECENT_POST_SEARCH_CACHE_TTL,
    current_utc_timestamp_text,
    expires_at_text,
    timestamp_is_expired,
)
from substitute.application.danbooru.preferences_service import (
    DanbooruPreferenceService,
)
from substitute.application.ports.danbooru_cache_repository import (
    DanbooruCacheRepository,
)
from substitute.domain.danbooru import (
    DanbooruCachedPost,
    DanbooruCachedPostSearch,
    DanbooruLookupStatus,
    DanbooruPostRecord,
)

_RECENT_POST_BATCH_SIZE = 10
_RECENT_POST_SCAN_CAP = 40


class DanbooruRecentPostsClient(Protocol):
    """Describe the client surface needed for tag-post gallery retrieval."""

    def list_posts_by_tag(
        self,
        tag_name: str,
        *,
        limit: int,
        before_post_id: int | None = None,
    ) -> tuple[DanbooruPostRecord, ...]:
        """Return one newest-first post batch for the supplied tag name."""


class DanbooruRecentPostsService:
    """Return recent visible Danbooru post ids for a wiki tag."""

    def __init__(
        self,
        *,
        client: DanbooruRecentPostsClient,
        cache_repository: DanbooruCacheRepository,
        preference_service: DanbooruPreferenceService,
    ) -> None:
        """Store the collaborators used for bounded recent-post lookups."""

        self._client = client
        self._cache_repository = cache_repository
        self._preference_service = preference_service

    def list_recent_visible_post_ids(
        self,
        tag_name: str,
        *,
        desired_count: int = 5,
    ) -> tuple[int, ...]:
        """Return up to ``desired_count`` visible recent post ids for one tag."""

        normalized_tag_name = tag_name.strip()
        if not normalized_tag_name or desired_count <= 0:
            return ()
        candidate_post_ids = self._candidate_post_ids_for_tag(
            normalized_tag_name,
            desired_count=desired_count,
        )
        visible_post_ids: list[int] = []
        for post_id in candidate_post_ids:
            cached_post = self._cache_repository.load_cached_post(post_id)
            if cached_post is None or cached_post.post is None:
                continue
            if not self._post_is_visible(cached_post.post):
                continue
            visible_post_ids.append(post_id)
            if len(visible_post_ids) >= desired_count:
                break
        return tuple(visible_post_ids)

    def _candidate_post_ids_for_tag(
        self,
        tag_name: str,
        *,
        desired_count: int,
    ) -> tuple[int, ...]:
        """Return cached or freshly fetched candidate ids for one tag."""

        cached_search = self._cache_repository.load_cached_post_search(tag_name)
        if cached_search is not None and not timestamp_is_expired(
            cached_search.expires_at
        ):
            return cached_search.post_ids
        fetched_post_ids = self._fetch_candidate_post_ids(
            tag_name,
            desired_count=desired_count,
        )
        if fetched_post_ids:
            self._cache_repository.save_cached_post_search(
                DanbooruCachedPostSearch(
                    tag_name=tag_name,
                    post_ids=fetched_post_ids,
                    fetched_at=current_utc_timestamp_text(),
                    expires_at=expires_at_text(RECENT_POST_SEARCH_CACHE_TTL),
                )
            )
            return fetched_post_ids
        if cached_search is not None:
            return cached_search.post_ids
        self._cache_repository.save_cached_post_search(
            DanbooruCachedPostSearch(
                tag_name=tag_name,
                post_ids=(),
                fetched_at=current_utc_timestamp_text(),
                expires_at=expires_at_text(RECENT_POST_SEARCH_CACHE_TTL),
            )
        )
        return ()

    def _fetch_candidate_post_ids(
        self,
        tag_name: str,
        *,
        desired_count: int,
    ) -> tuple[int, ...]:
        """Fetch one bounded candidate-post set for the supplied tag."""

        scanned_post_ids: list[int] = []
        visible_count = 0
        before_post_id: int | None = None
        while (
            len(scanned_post_ids) < _RECENT_POST_SCAN_CAP
            and visible_count < desired_count
        ):
            posts = self._client.list_posts_by_tag(
                tag_name,
                limit=_RECENT_POST_BATCH_SIZE,
                before_post_id=before_post_id,
            )
            if not posts:
                break
            for post in posts:
                self._cache_repository.save_cached_post(
                    DanbooruCachedPost(
                        post_id=post.post_id,
                        lookup_status=DanbooruLookupStatus.FOUND,
                        post=post,
                        fetched_at=current_utc_timestamp_text(),
                        expires_at=expires_at_text(POST_CACHE_TTL),
                    )
                )
                scanned_post_ids.append(post.post_id)
                if self._post_is_visible(post):
                    visible_count += 1
                if (
                    len(scanned_post_ids) >= _RECENT_POST_SCAN_CAP
                    or visible_count >= desired_count
                ):
                    break
            before_post_id = posts[-1].post_id
        return tuple(scanned_post_ids)

    def _post_is_visible(self, post: DanbooruPostRecord) -> bool:
        """Return whether one post can contribute a visible thumbnail tile."""

        if not self._preference_service.image_rating_is_allowed(post.rating):
            return False
        return bool(post.preview_file_url or post.large_file_url or post.file_url)


__all__ = ["DanbooruRecentPostsService"]

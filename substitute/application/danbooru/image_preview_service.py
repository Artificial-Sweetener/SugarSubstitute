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

"""Resolve Danbooru wiki image previews through cache and rating policy."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from itertools import count
from pathlib import Path
from typing import Protocol

from substitute.application.execution import (
    ExecutionContext,
    ScopedKeyedSingleFlight,
    TaskIdentity,
    TaskRequest,
    TaskSubmitter,
)
from substitute.application.danbooru.cache_policy import (
    IMAGE_PREVIEW_CACHE_TTL,
    NEGATIVE_LOOKUP_CACHE_TTL,
    POST_CACHE_TTL,
    current_utc_timestamp,
    expires_at_text,
    fetched_timestamp_is_stale,
    timestamp_is_expired,
)
from substitute.application.danbooru.content_models import (
    DanbooruImagePreviewState,
    DanbooruWikiImagePreview,
)
from substitute.application.danbooru.preferences_service import (
    DanbooruPreferenceService,
)
from substitute.application.ports.danbooru_cache_repository import (
    DanbooruCacheRepository,
)
from substitute.domain.danbooru import (
    DanbooruCachedImageAsset,
    DanbooruCachedPost,
    DanbooruLookupStatus,
    DanbooruMediaAssetLookupResult,
    DanbooruMediaAssetRecord,
    DanbooruMediaAssetVariantRecord,
    DanbooruPostLookupResult,
    DanbooruPostRecord,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("application.danbooru.image_preview_service")
_POST_BASE_URL = "https://danbooru.donmai.us/posts"
_MEDIA_ASSET_BASE_URL = "https://danbooru.donmai.us/media_assets"
_HIDDEN_BY_SETTINGS_MESSAGE = "Hidden by Danbooru content settings."
_UNAVAILABLE_MESSAGE = "Preview image is not available for this wiki embed."
_THUMBNAIL_TARGET_HEIGHT_PX = 156
_ASSET_PREVIEW_CACHE_KEY_VERSION = "best-fit-v1"


@dataclass(frozen=True, slots=True)
class _DanbooruSelectedPreviewSource:
    """Describe one chosen remote preview asset and its expected dimensions."""

    url: str
    width: int | None
    height: int | None


class DanbooruImagePreviewClient(Protocol):
    """Describe the client surface needed for cached preview image resolution."""

    def get_post_by_id(self, post_id: int) -> DanbooruPostLookupResult:
        """Return one Danbooru post by numeric identifier."""

    def get_media_asset_by_id(
        self,
        asset_id: int,
    ) -> DanbooruMediaAssetLookupResult:
        """Return one Danbooru media asset by numeric identifier."""

    def download_binary(self, url: str) -> bytes | None:
        """Return remote bytes for one preview URL when the request succeeds."""


class DanbooruImagePreviewService:
    """Serve Danbooru wiki image previews from cache with policy filtering.

    Preview-source selection is height-driven because the viewer renders a fixed
    thumbnail height. Danbooru's media-asset payload already reports the real
    post-variant dimensions after aspect-ratio reduction, so the smallest source
    whose reported height covers the rendered `156px` target is sufficient.
    Wider images naturally step up to larger variants because their preview
    heights collapse first.
    """

    def __init__(
        self,
        *,
        client: DanbooruImagePreviewClient,
        cache_repository: DanbooruCacheRepository,
        preference_service: DanbooruPreferenceService,
        refresh_submitter: TaskSubmitter,
    ) -> None:
        """Store the collaborators used for preview-image resolution."""

        self._client = client
        self._cache_repository = cache_repository
        self._preference_service = preference_service
        self._refresh_request_ids = count(1)
        self._refresh_single_flight: ScopedKeyedSingleFlight[
            tuple[str, int | str], None
        ] = ScopedKeyedSingleFlight(submitter=refresh_submitter)

    def shutdown(self) -> None:
        """Cancel active background refreshes owned by this service."""

        self._refresh_single_flight.cancel_all(reason="danbooru_image_service_shutdown")

    def resolve_preview_for_reference(
        self,
        *,
        source_kind: str,
        source_id: int,
    ) -> DanbooruWikiImagePreview:
        """Return one image preview or placeholder for the supplied wiki embed."""

        if source_kind == "asset":
            return self._resolve_preview_for_asset(source_id)
        return self._resolve_preview_for_post(source_id)

    def _resolve_preview_for_post(self, post_id: int) -> DanbooruWikiImagePreview:
        """Return one image preview or placeholder for the supplied post id."""

        post_record, post_is_stale = self._load_or_fetch_post(post_id)
        if post_is_stale:
            self._schedule_post_refresh(post_id)
        if post_record is None:
            return DanbooruWikiImagePreview(
                post_id=post_id,
                canonical_post_url=f"{_POST_BASE_URL}/{post_id}",
                state=DanbooruImagePreviewState.UNAVAILABLE,
                local_path=None,
                rating=None,
                width=None,
                height=None,
                hidden_reason=_UNAVAILABLE_MESSAGE,
            )
        if not self._image_is_allowed(post_record.rating):
            return DanbooruWikiImagePreview(
                post_id=post_id,
                canonical_post_url=f"{_POST_BASE_URL}/{post_id}",
                state=DanbooruImagePreviewState.HIDDEN,
                local_path=None,
                rating=post_record.rating,
                width=None,
                height=None,
                hidden_reason=_HIDDEN_BY_SETTINGS_MESSAGE,
            )

        preview_source = self._preview_source_for_post(post_record)
        if preview_source is None:
            return DanbooruWikiImagePreview(
                post_id=post_id,
                canonical_post_url=f"{_POST_BASE_URL}/{post_id}",
                state=DanbooruImagePreviewState.UNAVAILABLE,
                local_path=None,
                rating=post_record.rating,
                width=None,
                height=None,
                hidden_reason=_UNAVAILABLE_MESSAGE,
            )
        cache_key = f"post-preview:{post_id}:{preview_source.url}"
        cached_asset = self._cache_repository.load_cached_image_asset(cache_key)
        if cached_asset is not None:
            if fetched_timestamp_is_stale(
                cached_asset.fetched_at,
                ttl=IMAGE_PREVIEW_CACHE_TTL,
            ):
                self._schedule_image_refresh(
                    cache_key,
                    rating=post_record.rating,
                    preview_source=preview_source,
                )
            self._cache_repository.touch_cached_image_asset(
                cache_key,
                last_used_at=current_utc_timestamp().isoformat(),
            )
            return DanbooruWikiImagePreview(
                post_id=post_id,
                canonical_post_url=f"{_POST_BASE_URL}/{post_id}",
                state=DanbooruImagePreviewState.READY,
                local_path=cached_asset.local_path,
                rating=post_record.rating,
                width=cached_asset.width,
                height=cached_asset.height,
            )

        image_bytes = self._client.download_binary(preview_source.url)
        if image_bytes is None:
            return DanbooruWikiImagePreview(
                post_id=post_id,
                canonical_post_url=f"{_POST_BASE_URL}/{post_id}",
                state=DanbooruImagePreviewState.UNAVAILABLE,
                local_path=None,
                rating=post_record.rating,
                width=None,
                height=None,
                hidden_reason=_UNAVAILABLE_MESSAGE,
            )
        now_text = current_utc_timestamp().isoformat()
        stored_asset = self._cache_repository.save_cached_image_asset(
            DanbooruCachedImageAsset(
                cache_key=cache_key,
                source_url=preview_source.url,
                local_path=_preview_path_hint(preview_source.url),
                rating=post_record.rating,
                width=preview_source.width,
                height=preview_source.height,
                fetched_at=now_text,
                last_used_at=now_text,
                byte_size=0,
            ),
            image_bytes,
        )
        return DanbooruWikiImagePreview(
            post_id=post_id,
            canonical_post_url=f"{_POST_BASE_URL}/{post_id}",
            state=DanbooruImagePreviewState.READY,
            local_path=stored_asset.local_path,
            rating=post_record.rating,
            width=stored_asset.width,
            height=stored_asset.height,
        )

    def _resolve_preview_for_asset(self, asset_id: int) -> DanbooruWikiImagePreview:
        """Return one image preview or placeholder for the supplied asset id."""

        cache_key = f"asset-preview:{_ASSET_PREVIEW_CACHE_KEY_VERSION}:{asset_id}"
        cached_asset = self._cache_repository.load_cached_image_asset(cache_key)
        if cached_asset is not None:
            if not self._image_is_allowed(cached_asset.rating, allow_unknown=True):
                return DanbooruWikiImagePreview(
                    post_id=asset_id,
                    canonical_post_url=f"{_MEDIA_ASSET_BASE_URL}/{asset_id}",
                    state=DanbooruImagePreviewState.HIDDEN,
                    local_path=None,
                    rating=cached_asset.rating,
                    width=None,
                    height=None,
                    hidden_reason=_HIDDEN_BY_SETTINGS_MESSAGE,
                )
            if fetched_timestamp_is_stale(
                cached_asset.fetched_at,
                ttl=IMAGE_PREVIEW_CACHE_TTL,
            ):
                self._schedule_image_refresh(
                    cache_key,
                    rating=cached_asset.rating,
                    preview_source=_DanbooruSelectedPreviewSource(
                        url=cached_asset.source_url,
                        width=cached_asset.width,
                        height=cached_asset.height,
                    ),
                )
            self._cache_repository.touch_cached_image_asset(
                cache_key,
                last_used_at=current_utc_timestamp().isoformat(),
            )
            return DanbooruWikiImagePreview(
                post_id=asset_id,
                canonical_post_url=f"{_MEDIA_ASSET_BASE_URL}/{asset_id}",
                state=DanbooruImagePreviewState.READY,
                local_path=cached_asset.local_path,
                rating=cached_asset.rating,
                width=cached_asset.width,
                height=cached_asset.height,
            )

        asset_result = self._client.get_media_asset_by_id(asset_id)
        if asset_result.status is not DanbooruLookupStatus.FOUND:
            return DanbooruWikiImagePreview(
                post_id=asset_id,
                canonical_post_url=f"{_MEDIA_ASSET_BASE_URL}/{asset_id}",
                state=DanbooruImagePreviewState.UNAVAILABLE,
                local_path=None,
                rating=None,
                width=None,
                height=None,
                hidden_reason=_UNAVAILABLE_MESSAGE,
            )
        asset_record = asset_result.media_asset
        assert asset_record is not None
        preview_source = self._preview_source_for_asset(asset_record)
        if preview_source is None:
            return DanbooruWikiImagePreview(
                post_id=asset_id,
                canonical_post_url=f"{_MEDIA_ASSET_BASE_URL}/{asset_id}",
                state=DanbooruImagePreviewState.UNAVAILABLE,
                local_path=None,
                rating=None,
                width=None,
                height=None,
                hidden_reason=_UNAVAILABLE_MESSAGE,
            )
        rating = None
        if not self._image_is_allowed(rating, allow_unknown=True):
            return DanbooruWikiImagePreview(
                post_id=asset_id,
                canonical_post_url=f"{_MEDIA_ASSET_BASE_URL}/{asset_id}",
                state=DanbooruImagePreviewState.HIDDEN,
                local_path=None,
                rating=rating,
                width=None,
                height=None,
                hidden_reason=_HIDDEN_BY_SETTINGS_MESSAGE,
            )
        image_bytes = self._client.download_binary(preview_source.url)
        if image_bytes is None:
            return DanbooruWikiImagePreview(
                post_id=asset_id,
                canonical_post_url=f"{_MEDIA_ASSET_BASE_URL}/{asset_id}",
                state=DanbooruImagePreviewState.UNAVAILABLE,
                local_path=None,
                rating=rating,
                width=None,
                height=None,
                hidden_reason=_UNAVAILABLE_MESSAGE,
            )
        now_text = current_utc_timestamp().isoformat()
        stored_asset = self._cache_repository.save_cached_image_asset(
            DanbooruCachedImageAsset(
                cache_key=cache_key,
                source_url=preview_source.url,
                local_path=_preview_path_hint(preview_source.url),
                rating=rating,
                width=preview_source.width,
                height=preview_source.height,
                fetched_at=now_text,
                last_used_at=now_text,
                byte_size=0,
            ),
            image_bytes,
        )
        return DanbooruWikiImagePreview(
            post_id=asset_id,
            canonical_post_url=f"{_MEDIA_ASSET_BASE_URL}/{asset_id}",
            state=DanbooruImagePreviewState.READY,
            local_path=stored_asset.local_path,
            rating=rating,
            width=stored_asset.width,
            height=stored_asset.height,
        )

    def _load_or_fetch_post(
        self,
        post_id: int,
    ) -> tuple[DanbooruPostRecord | None, bool]:
        """Return cached post metadata for one post id, fetching when absent."""

        cached_entry = self._cache_repository.load_cached_post(post_id)
        if cached_entry is not None:
            is_stale = timestamp_is_expired(cached_entry.expires_at)
            if cached_entry.lookup_status is DanbooruLookupStatus.FOUND:
                return cached_entry.post, is_stale
            if cached_entry.lookup_status is DanbooruLookupStatus.NOT_FOUND:
                return None, is_stale
        fetched = self._fetch_post(post_id)
        if fetched.status is DanbooruLookupStatus.FOUND:
            return fetched.post, False
        return None, False

    def _fetch_post(self, post_id: int) -> DanbooruPostLookupResult:
        """Fetch one post record from Danbooru and persist the cache result."""

        result = self._client.get_post_by_id(post_id)
        now = current_utc_timestamp()
        self._cache_repository.save_cached_post(
            DanbooruCachedPost(
                post_id=post_id,
                lookup_status=result.status,
                post=result.post,
                fetched_at=now.isoformat(),
                expires_at=expires_at_text(
                    POST_CACHE_TTL
                    if result.status is DanbooruLookupStatus.FOUND
                    else NEGATIVE_LOOKUP_CACHE_TTL,
                    now=now,
                ),
                error=result.error,
            )
        )
        return result

    def _schedule_post_refresh(self, post_id: int) -> None:
        """Schedule a stale post metadata refresh when preferences allow it."""

        if not self._preference_service.load_preferences().background_refresh_enabled:
            return
        self._schedule_refresh(("post", post_id), lambda: self._fetch_post(post_id))

    def _schedule_image_refresh(
        self,
        cache_key: str,
        *,
        rating: str | None,
        preview_source: _DanbooruSelectedPreviewSource,
    ) -> None:
        """Schedule a stale image preview refresh when preferences allow it."""

        if not self._preference_service.load_preferences().background_refresh_enabled:
            return

        def refresh_image() -> None:
            """Refresh one cached preview image from its remote preview URL."""

            image_bytes = self._client.download_binary(preview_source.url)
            if image_bytes is None:
                return
            now_text = current_utc_timestamp().isoformat()
            self._cache_repository.save_cached_image_asset(
                DanbooruCachedImageAsset(
                    cache_key=cache_key,
                    source_url=preview_source.url,
                    local_path=_preview_path_hint(preview_source.url),
                    rating=rating,
                    width=preview_source.width,
                    height=preview_source.height,
                    fetched_at=now_text,
                    last_used_at=now_text,
                    byte_size=0,
                ),
                image_bytes,
            )

        self._schedule_refresh(("image", cache_key), refresh_image)

    def _schedule_refresh(
        self,
        cache_key: tuple[str, int | str],
        operation: Callable[[], object],
    ) -> None:
        """Schedule one cache refresh operation at most once per cache key."""

        def refresh_task() -> None:
            """Refresh one cached entity through a coalesced execution request."""

            try:
                operation()
            except Exception as error:
                log_warning(
                    _LOGGER,
                    "Danbooru image refresh failed.",
                    cache_key=f"{cache_key[0]}:{cache_key[1]}",
                    error=repr(error),
                )

        request: TaskRequest[None] = TaskRequest(
            identity=TaskIdentity(
                request_id=next(self._refresh_request_ids),
                domain="danbooru_image_refresh",
                parts=(("kind", cache_key[0]), ("key", cache_key[1])),
            ),
            context=ExecutionContext(
                operation="danbooru_image_refresh",
                reason=cache_key[0],
                lane="danbooru_refresh",
                safe_fields=(("kind", cache_key[0]),),
            ),
            work=lambda _cancellation: refresh_task(),
        )
        try:
            self._refresh_single_flight.submit(
                cache_key,
                request,
            )
        except Exception as error:
            log_warning(
                _LOGGER,
                "Danbooru image refresh submission failed.",
                cache_key=f"{cache_key[0]}:{cache_key[1]}",
                error=repr(error),
            )

    @staticmethod
    def _preview_source_for_post(
        post_record: DanbooruPostRecord,
    ) -> _DanbooruSelectedPreviewSource | None:
        """Return the preferred bounded preview source for one Danbooru post."""

        selected_url = (
            post_record.large_file_url
            or post_record.preview_file_url
            or post_record.file_url
        )
        if selected_url is None:
            return None
        return _DanbooruSelectedPreviewSource(
            url=selected_url,
            width=None,
            height=None,
        )

    @staticmethod
    def _preview_source_for_asset(
        asset_record: DanbooruMediaAssetRecord,
    ) -> _DanbooruSelectedPreviewSource | None:
        """Return the smallest sufficient preview source for one media asset."""

        threshold_height = _minimum_source_height_for_thumbnail()
        bounded_variants = tuple(
            variant
            for variant in asset_record.variants
            if variant.variant_type not in {"sample", "original"}
        )
        qualifying_variants = sorted(
            (
                variant
                for variant in bounded_variants
                if variant.height is not None and variant.height >= threshold_height
            ),
            key=lambda variant: (
                variant.height,
                variant.width if variant.width is not None else 0,
            ),
        )
        if qualifying_variants:
            return _selected_preview_source(qualifying_variants[0])
        sample_variant = _variant_by_type(asset_record.variants, "sample")
        if sample_variant is not None:
            return _selected_preview_source(sample_variant)
        bounded_fallbacks = sorted(
            bounded_variants,
            key=lambda variant: (
                variant.height if variant.height is not None else -1,
                variant.width if variant.width is not None else -1,
            ),
            reverse=True,
        )
        if bounded_fallbacks:
            return _selected_preview_source(bounded_fallbacks[0])
        original_variant = _variant_by_type(asset_record.variants, "original")
        if original_variant is not None:
            return _selected_preview_source(original_variant)
        return None

    def _image_is_allowed(
        self,
        rating: str | None,
        *,
        allow_unknown: bool = False,
    ) -> bool:
        """Return whether one wiki image may render under the current preferences."""

        preferences = self._preference_service.load_preferences()
        if not preferences.show_wiki_images:
            return False
        if rating is None:
            return allow_unknown
        return self._preference_service.image_rating_is_allowed(rating)


def _preview_path_hint(preview_url: str) -> Path:
    """Return a stable file-name hint for one preview URL."""

    return Path(preview_url.rsplit("/", 1)[-1] or "preview.img")


def _thumbnail_target_height_px() -> int:
    """Return the rendered wiki-thumbnail height used by the viewer."""

    return _THUMBNAIL_TARGET_HEIGHT_PX


def _minimum_source_height_for_thumbnail() -> int:
    """Return the minimum remote height that avoids upscaling in the viewer.

    Danbooru media-asset variants already report their real post-resized heights
    after aspect-ratio reduction. Matching the rendered thumbnail height is
    therefore enough to keep portrait previews small while forcing wider images
    onto the next larger bounded variant when the tiny preview would upscale.
    """

    return _thumbnail_target_height_px()


def _variant_by_type(
    variants: tuple[DanbooruMediaAssetVariantRecord, ...],
    variant_type: str,
) -> DanbooruMediaAssetVariantRecord | None:
    """Return the first media-asset variant matching one Danbooru type name."""

    for variant in variants:
        if variant.variant_type == variant_type:
            return variant
    return None


def _selected_preview_source(
    variant: DanbooruMediaAssetVariantRecord,
) -> _DanbooruSelectedPreviewSource:
    """Return one cache/download preview descriptor from a media-asset variant."""

    return _DanbooruSelectedPreviewSource(
        url=variant.url,
        width=variant.width,
        height=variant.height,
    )


__all__ = ["DanbooruImagePreviewClient", "DanbooruImagePreviewService"]

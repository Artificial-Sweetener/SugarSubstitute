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

"""Provide typed collaborators and records for image-preview service tests."""

from __future__ import annotations

from pathlib import Path

from substitute.application.danbooru.image_preview_service import (
    DanbooruImagePreviewService,
)
from substitute.application.danbooru.preferences_service import (
    DanbooruPreferenceService,
)
from substitute.domain.danbooru import (
    DanbooruMediaAssetLookupResult,
    DanbooruMediaAssetRecord,
    DanbooruMediaAssetVariantRecord,
    DanbooruPostLookupResult,
    DanbooruPostRecord,
)
from substitute.domain.danbooru.preferences import (
    DanbooruPreferences,
    default_danbooru_preferences,
)
from tests.support.execution import ImmediateTaskSubmitter
from tests.support.danbooru_cache_repository import build_danbooru_cache_repository


class StubDanbooruImagePreviewClient:
    """Return deterministic metadata and binary payloads while recording calls."""

    def __init__(
        self,
        *,
        post_results_by_id: dict[int, DanbooruPostLookupResult],
        media_asset_results_by_id: dict[int, DanbooruMediaAssetLookupResult]
        | None = None,
        binary_payloads_by_url: dict[str, bytes] | None = None,
    ) -> None:
        """Store deterministic responses for every image-preview client boundary."""

        self._post_results_by_id = dict(post_results_by_id)
        self._media_asset_results_by_id = dict(media_asset_results_by_id or {})
        self._binary_payloads_by_url = dict(binary_payloads_by_url or {})
        self.calls: list[tuple[str, str]] = []

    def get_post_by_id(self, post_id: int) -> DanbooruPostLookupResult:
        """Return one configured post lookup and record its identifier."""

        self.calls.append(("post", str(post_id)))
        return self._post_results_by_id[post_id]

    def get_media_asset_by_id(self, asset_id: int) -> DanbooruMediaAssetLookupResult:
        """Return one configured media-asset lookup and record its identifier."""

        self.calls.append(("asset", str(asset_id)))
        return self._media_asset_results_by_id[asset_id]

    def download_binary(self, url: str) -> bytes | None:
        """Return one configured binary payload and record its URL."""

        self.calls.append(("binary", url))
        return self._binary_payloads_by_url.get(url)


class MemoryDanbooruPreferenceRepository:
    """Persist one typed Danbooru preference snapshot in memory."""

    def __init__(self) -> None:
        """Initialize the repository with production defaults."""

        self.preferences = default_danbooru_preferences()

    def load(self) -> DanbooruPreferences:
        """Return the current preference snapshot."""

        return self.preferences

    def save(self, preferences: DanbooruPreferences) -> None:
        """Replace the current preference snapshot."""

        self.preferences = preferences


def build_image_preview_service(
    tmp_path: Path,
    *,
    client: StubDanbooruImagePreviewClient,
) -> DanbooruImagePreviewService:
    """Build one cached image-preview service with deterministic boundaries."""

    return DanbooruImagePreviewService(
        client=client,
        cache_repository=build_danbooru_cache_repository(tmp_path),
        preference_service=DanbooruPreferenceService(
            MemoryDanbooruPreferenceRepository()
        ),
        refresh_submitter=ImmediateTaskSubmitter(),
    )


def post_record(
    *,
    post_id: int,
    large_file_url: str | None,
    preview_file_url: str,
    rating: str,
) -> DanbooruPostRecord:
    """Build one representative Danbooru post record."""

    return DanbooruPostRecord(
        post_id=post_id,
        created_at="2026-05-01T10:00:00.000-04:00",
        updated_at="2026-05-13T12:30:00.000-04:00",
        source=f"https://artist.example/post/{post_id}",
        md5="0123456789abcdef0123456789abcdef",
        rating=rating,
        tag_string="1girl long_hair smile",
        tag_string_general="1girl long_hair smile",
        tag_string_artist="artist_name",
        tag_string_copyright="series_name",
        tag_string_character="heroine",
        tag_string_meta="commentary",
        file_url="https://cdn.donmai.us/original/example.jpg",
        large_file_url=large_file_url,
        preview_file_url=preview_file_url,
    )


def media_asset_record(
    *,
    asset_id: int,
    image_width: int,
    image_height: int,
    variants: tuple[DanbooruMediaAssetVariantRecord, ...],
) -> DanbooruMediaAssetRecord:
    """Build one representative Danbooru media-asset record."""

    return DanbooruMediaAssetRecord(
        asset_id=asset_id,
        created_at="2025-11-21T20:45:36.958-05:00",
        updated_at="2025-11-21T20:45:38.328-05:00",
        md5="c7eedd90ff57e6741953cc32ed34e95a",
        file_ext="jpg",
        image_width=image_width,
        image_height=image_height,
        variants=variants,
    )


def asset_variant(
    *,
    variant_type: str,
    url: str,
    width: int,
    height: int,
) -> DanbooruMediaAssetVariantRecord:
    """Build one representative media-asset variant."""

    return DanbooruMediaAssetVariantRecord(
        variant_type=variant_type,
        url=url,
        width=width,
        height=height,
        file_ext="jpg",
    )


__all__ = [
    "StubDanbooruImagePreviewClient",
    "asset_variant",
    "build_image_preview_service",
    "media_asset_record",
    "post_record",
]

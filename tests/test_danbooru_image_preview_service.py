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

"""Unit tests for cached Danbooru wiki image preview resolution."""

from __future__ import annotations

from pathlib import Path

from tests.execution_testing import ImmediateTaskSubmitter
from substitute.application.danbooru.content_models import (
    DanbooruImagePreviewState,
)
from substitute.application.danbooru.image_preview_service import (
    DanbooruImagePreviewService,
)
from substitute.application.danbooru.preferences_service import (
    DanbooruPreferenceService,
)
from substitute.domain.danbooru import (
    DanbooruLookupStatus,
    DanbooruMediaAssetLookupResult,
    DanbooruMediaAssetRecord,
    DanbooruMediaAssetVariantRecord,
    DanbooruPostLookupResult,
    DanbooruPostRecord,
)
from substitute.domain.danbooru.preferences import (
    DanbooruImageRatingPolicy,
)
from substitute.infrastructure.persistence.danbooru_cache_store import (
    SqliteDanbooruCacheStore,
)


class _StubDanbooruImagePreviewClient:
    """Provide deterministic post metadata and preview bytes for tests."""

    def __init__(
        self,
        *,
        post_results_by_id: dict[int, DanbooruPostLookupResult],
        media_asset_results_by_id: dict[int, DanbooruMediaAssetLookupResult]
        | None = None,
        binary_payloads_by_url: dict[str, bytes] | None = None,
    ) -> None:
        """Store deterministic preview responses and capture each call."""

        self._post_results_by_id = dict(post_results_by_id)
        self._media_asset_results_by_id = dict(media_asset_results_by_id or {})
        self._binary_payloads_by_url = dict(binary_payloads_by_url or {})
        self.calls: list[tuple[str, str]] = []

    def get_post_by_id(self, post_id: int) -> DanbooruPostLookupResult:
        """Return the configured post result for the requested identifier."""

        self.calls.append(("post", str(post_id)))
        return self._post_results_by_id[post_id]

    def get_media_asset_by_id(self, asset_id: int) -> DanbooruMediaAssetLookupResult:
        """Return the configured media asset result for the requested identifier."""

        self.calls.append(("asset", str(asset_id)))
        return self._media_asset_results_by_id[asset_id]

    def download_binary(self, url: str) -> bytes | None:
        """Return the configured binary payload for the requested URL."""

        self.calls.append(("binary", url))
        return self._binary_payloads_by_url.get(url)


class _MemoryDanbooruPreferenceRepository:
    """Persist Danbooru preferences in memory for unit tests."""

    def __init__(self) -> None:
        """Initialize with default Danbooru preferences."""

        self.preferences = DanbooruPreferenceService(
            _NullDanbooruPreferenceRepository()
        ).default_preferences()

    def load(self):  # type: ignore[no-untyped-def]
        """Return the current preference snapshot."""

        return self.preferences

    def save(self, preferences):  # type: ignore[no-untyped-def]
        """Persist one preference snapshot in memory."""

        self.preferences = preferences


class _NullDanbooruPreferenceRepository:
    """Return default Danbooru preferences for service bootstrapping."""

    def load(self):  # type: ignore[no-untyped-def]
        """Return the default Danbooru preferences."""

        return DanbooruPreferenceService(self).default_preferences()

    def save(self, preferences):  # type: ignore[no-untyped-def]
        """Ignore persisted writes from default bootstrapping."""


def test_image_preview_service_downloads_and_caches_safe_previews(
    tmp_path: Path,
) -> None:
    """Post previews should prefer the larger bounded sample asset first."""

    sample_url = "https://cdn.donmai.us/sample/example.jpg"
    client = _StubDanbooruImagePreviewClient(
        post_results_by_id={
            101: DanbooruPostLookupResult(
                status=DanbooruLookupStatus.FOUND,
                post=_post_record(
                    post_id=101,
                    large_file_url=sample_url,
                    preview_file_url="https://cdn.donmai.us/180x180/example.jpg",
                    rating="s",
                ),
            )
        },
        binary_payloads_by_url={sample_url: b"image-bytes"},
    )
    service = _service(tmp_path, client=client)

    first = service.resolve_preview_for_reference(source_kind="post", source_id=101)
    second = service.resolve_preview_for_reference(source_kind="post", source_id=101)

    assert first.state is DanbooruImagePreviewState.READY
    assert first.local_path is not None
    assert first.local_path.read_bytes() == b"image-bytes"
    assert second.state is DanbooruImagePreviewState.READY
    assert client.calls == [("post", "101"), ("binary", sample_url)]


def test_image_preview_service_falls_back_to_post_preview_when_sample_is_absent(
    tmp_path: Path,
) -> None:
    """Post previews should still use the tiny preview when no sample exists."""

    preview_url = "https://cdn.donmai.us/180x180/example.jpg"
    client = _StubDanbooruImagePreviewClient(
        post_results_by_id={
            111: DanbooruPostLookupResult(
                status=DanbooruLookupStatus.FOUND,
                post=_post_record(
                    post_id=111,
                    large_file_url=None,
                    preview_file_url=preview_url,
                    rating="s",
                ),
            )
        },
        binary_payloads_by_url={preview_url: b"preview-image-bytes"},
    )
    service = _service(tmp_path, client=client)

    result = service.resolve_preview_for_reference(source_kind="post", source_id=111)

    assert result.state is DanbooruImagePreviewState.READY
    assert result.local_path is not None
    assert result.local_path.read_bytes() == b"preview-image-bytes"
    assert client.calls == [("post", "111"), ("binary", preview_url)]


def test_image_preview_service_hides_blocked_ratings_without_downloading(
    tmp_path: Path,
) -> None:
    """Explicit previews should respect the configured Danbooru image policy."""

    preview_url = "https://cdn.donmai.us/180x180/example-explicit.jpg"
    client = _StubDanbooruImagePreviewClient(
        post_results_by_id={
            202: DanbooruPostLookupResult(
                status=DanbooruLookupStatus.FOUND,
                post=_post_record(
                    post_id=202,
                    large_file_url="https://cdn.donmai.us/sample/example-explicit.jpg",
                    preview_file_url=preview_url,
                    rating="e",
                ),
            )
        },
        binary_payloads_by_url={preview_url: b"image-bytes"},
    )
    service = _service(tmp_path, client=client)
    service._preference_service.set_allowed_image_ratings(
        DanbooruImageRatingPolicy.SAFE_ONLY
    )

    result = service.resolve_preview_for_reference(source_kind="post", source_id=202)

    assert result.state is DanbooruImagePreviewState.HIDDEN
    assert "Hidden by Danbooru content settings." == result.hidden_reason
    assert client.calls == [("post", "202")]


def test_image_preview_service_allows_general_rating_when_policy_is_all(
    tmp_path: Path,
) -> None:
    """General-rated Danbooru previews should render under the all-ratings policy."""

    sample_url = "https://cdn.donmai.us/sample/example-general.jpg"
    client = _StubDanbooruImagePreviewClient(
        post_results_by_id={
            303: DanbooruPostLookupResult(
                status=DanbooruLookupStatus.FOUND,
                post=_post_record(
                    post_id=303,
                    large_file_url=sample_url,
                    preview_file_url="https://cdn.donmai.us/180x180/example-general.jpg",
                    rating="g",
                ),
            )
        },
        binary_payloads_by_url={sample_url: b"general-image-bytes"},
    )
    service = _service(tmp_path, client=client)
    service._preference_service.set_allowed_image_ratings(
        DanbooruImageRatingPolicy.ALL_RATINGS
    )

    result = service.resolve_preview_for_reference(source_kind="post", source_id=303)

    assert result.state is DanbooruImagePreviewState.READY
    assert result.local_path is not None
    assert result.local_path.read_bytes() == b"general-image-bytes"


def test_image_preview_service_downloads_asset_embeds_without_raw_dtext_leak(
    tmp_path: Path,
) -> None:
    """Asset previews should choose the smallest variant that covers 156px tall."""

    chosen_url = "https://cdn.donmai.us/360x360/example-asset.jpg"
    client = _StubDanbooruImagePreviewClient(
        post_results_by_id={},
        media_asset_results_by_id={
            37448022: DanbooruMediaAssetLookupResult(
                status=DanbooruLookupStatus.FOUND,
                media_asset=_media_asset_record(
                    asset_id=37448022,
                    image_width=1280,
                    image_height=720,
                    variants=(
                        _asset_variant(
                            variant_type="180x180",
                            url="https://cdn.donmai.us/180x180/example-asset.jpg",
                            width=180,
                            height=101,
                        ),
                        _asset_variant(
                            variant_type="360x360",
                            url=chosen_url,
                            width=360,
                            height=203,
                        ),
                        _asset_variant(
                            variant_type="sample",
                            url="https://cdn.donmai.us/sample/example-asset.jpg",
                            width=850,
                            height=478,
                        ),
                        _asset_variant(
                            variant_type="original",
                            url="https://cdn.donmai.us/original/example-asset.jpg",
                            width=1280,
                            height=720,
                        ),
                    ),
                ),
            )
        },
        binary_payloads_by_url={chosen_url: b"asset-image-bytes"},
    )
    service = _service(tmp_path, client=client)

    first = service.resolve_preview_for_reference(
        source_kind="asset",
        source_id=37448022,
    )
    second = service.resolve_preview_for_reference(
        source_kind="asset",
        source_id=37448022,
    )

    assert first.state is DanbooruImagePreviewState.READY
    assert first.local_path is not None
    assert first.local_path.read_bytes() == b"asset-image-bytes"
    assert first.width == 360
    assert first.height == 203
    assert second.state is DanbooruImagePreviewState.READY
    assert client.calls == [("asset", "37448022"), ("binary", chosen_url)]


def test_image_preview_service_uses_asset_sample_before_original_when_variants_are_too_small(
    tmp_path: Path,
) -> None:
    """Asset previews should fall back to sample before original when needed."""

    sample_url = "https://cdn.donmai.us/sample/example-asset.jpg"
    client = _StubDanbooruImagePreviewClient(
        post_results_by_id={},
        media_asset_results_by_id={
            400: DanbooruMediaAssetLookupResult(
                status=DanbooruLookupStatus.FOUND,
                media_asset=_media_asset_record(
                    asset_id=400,
                    image_width=2100,
                    image_height=700,
                    variants=(
                        _asset_variant(
                            variant_type="180x180",
                            url="https://cdn.donmai.us/180x180/example-asset.jpg",
                            width=180,
                            height=60,
                        ),
                        _asset_variant(
                            variant_type="360x360",
                            url="https://cdn.donmai.us/360x360/example-asset.jpg",
                            width=360,
                            height=120,
                        ),
                        _asset_variant(
                            variant_type="720x720",
                            url="https://cdn.donmai.us/720x720/example-asset.webp",
                            width=720,
                            height=140,
                        ),
                        _asset_variant(
                            variant_type="sample",
                            url=sample_url,
                            width=850,
                            height=283,
                        ),
                        _asset_variant(
                            variant_type="original",
                            url="https://cdn.donmai.us/original/example-asset.jpg",
                            width=2100,
                            height=700,
                        ),
                    ),
                ),
            )
        },
        binary_payloads_by_url={sample_url: b"sample-asset-image-bytes"},
    )
    service = _service(tmp_path, client=client)

    result = service.resolve_preview_for_reference(source_kind="asset", source_id=400)

    assert result.state is DanbooruImagePreviewState.READY
    assert result.local_path is not None
    assert result.local_path.read_bytes() == b"sample-asset-image-bytes"
    assert client.calls == [("asset", "400"), ("binary", sample_url)]


def _service(
    tmp_path: Path,
    *,
    client: _StubDanbooruImagePreviewClient,
) -> DanbooruImagePreviewService:
    """Create one cached image preview service for tests."""

    preference_service = DanbooruPreferenceService(
        _MemoryDanbooruPreferenceRepository()
    )
    service = DanbooruImagePreviewService(
        client=client,
        cache_repository=SqliteDanbooruCacheStore(tmp_path),
        preference_service=preference_service,
        refresh_submitter=ImmediateTaskSubmitter(),
    )
    return service


def _post_record(
    *,
    post_id: int,
    large_file_url: str | None,
    preview_file_url: str,
    rating: str,
) -> DanbooruPostRecord:
    """Return one representative Danbooru post record for image preview tests."""

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


def _media_asset_record(
    *,
    asset_id: int,
    image_width: int,
    image_height: int,
    variants: tuple[DanbooruMediaAssetVariantRecord, ...],
) -> DanbooruMediaAssetRecord:
    """Return one representative Danbooru media-asset record for tests."""

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


def _asset_variant(
    *,
    variant_type: str,
    url: str,
    width: int,
    height: int,
) -> DanbooruMediaAssetVariantRecord:
    """Return one representative Danbooru media-asset variant for tests."""

    return DanbooruMediaAssetVariantRecord(
        variant_type=variant_type,
        url=url,
        width=width,
        height=height,
        file_ext="jpg",
    )

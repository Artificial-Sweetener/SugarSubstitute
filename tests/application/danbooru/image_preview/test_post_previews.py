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

"""Test cached Danbooru post image-preview selection and content policy."""

from __future__ import annotations

from pathlib import Path

from substitute.application.danbooru.content_models import DanbooruImagePreviewState
from substitute.domain.danbooru import DanbooruLookupStatus, DanbooruPostLookupResult
from substitute.domain.danbooru.preferences import DanbooruImageRatingPolicy
from tests.application.danbooru.image_preview.collaborators import (
    StubDanbooruImagePreviewClient,
    build_image_preview_service,
    post_record,
)


def test_downloads_and_caches_safe_sample_preview(tmp_path: Path) -> None:
    """Prefer and cache the larger bounded sample for an allowed post."""

    sample_url = "https://cdn.donmai.us/sample/example.jpg"
    client = StubDanbooruImagePreviewClient(
        post_results_by_id={
            101: DanbooruPostLookupResult(
                status=DanbooruLookupStatus.FOUND,
                post=post_record(
                    post_id=101,
                    large_file_url=sample_url,
                    preview_file_url="https://cdn.donmai.us/180x180/example.jpg",
                    rating="s",
                ),
            )
        },
        binary_payloads_by_url={sample_url: b"image-bytes"},
    )
    service = build_image_preview_service(tmp_path, client=client)

    first = service.resolve_preview_for_reference(source_kind="post", source_id=101)
    second = service.resolve_preview_for_reference(source_kind="post", source_id=101)

    assert first.state is DanbooruImagePreviewState.READY
    assert first.local_path is not None
    assert first.local_path.read_bytes() == b"image-bytes"
    assert second.state is DanbooruImagePreviewState.READY
    assert client.calls == [("post", "101"), ("binary", sample_url)]


def test_falls_back_to_small_preview_without_sample(tmp_path: Path) -> None:
    """Use the small post preview when no bounded sample URL exists."""

    preview_url = "https://cdn.donmai.us/180x180/example.jpg"
    client = StubDanbooruImagePreviewClient(
        post_results_by_id={
            111: DanbooruPostLookupResult(
                status=DanbooruLookupStatus.FOUND,
                post=post_record(
                    post_id=111,
                    large_file_url=None,
                    preview_file_url=preview_url,
                    rating="s",
                ),
            )
        },
        binary_payloads_by_url={preview_url: b"preview-image-bytes"},
    )
    service = build_image_preview_service(tmp_path, client=client)

    result = service.resolve_preview_for_reference(source_kind="post", source_id=111)

    assert result.state is DanbooruImagePreviewState.READY
    assert result.local_path is not None
    assert result.local_path.read_bytes() == b"preview-image-bytes"
    assert client.calls == [("post", "111"), ("binary", preview_url)]


def test_hides_blocked_rating_without_download(tmp_path: Path) -> None:
    """Stop at metadata when the configured image policy blocks a rating."""

    preview_url = "https://cdn.donmai.us/180x180/example-explicit.jpg"
    client = StubDanbooruImagePreviewClient(
        post_results_by_id={
            202: DanbooruPostLookupResult(
                status=DanbooruLookupStatus.FOUND,
                post=post_record(
                    post_id=202,
                    large_file_url="https://cdn.donmai.us/sample/example-explicit.jpg",
                    preview_file_url=preview_url,
                    rating="e",
                ),
            )
        },
        binary_payloads_by_url={preview_url: b"image-bytes"},
    )
    service = build_image_preview_service(tmp_path, client=client)
    service._preference_service.set_allowed_image_ratings(
        DanbooruImageRatingPolicy.SAFE_ONLY
    )

    result = service.resolve_preview_for_reference(source_kind="post", source_id=202)

    assert result.state is DanbooruImagePreviewState.HIDDEN
    assert result.hidden_reason == "Hidden by Danbooru content settings."
    assert client.calls == [("post", "202")]


def test_all_ratings_policy_allows_general_preview(tmp_path: Path) -> None:
    """Download a general-rated preview under the all-ratings policy."""

    sample_url = "https://cdn.donmai.us/sample/example-general.jpg"
    client = StubDanbooruImagePreviewClient(
        post_results_by_id={
            303: DanbooruPostLookupResult(
                status=DanbooruLookupStatus.FOUND,
                post=post_record(
                    post_id=303,
                    large_file_url=sample_url,
                    preview_file_url=(
                        "https://cdn.donmai.us/180x180/example-general.jpg"
                    ),
                    rating="g",
                ),
            )
        },
        binary_payloads_by_url={sample_url: b"general-image-bytes"},
    )
    service = build_image_preview_service(tmp_path, client=client)
    service._preference_service.set_allowed_image_ratings(
        DanbooruImageRatingPolicy.ALL_RATINGS
    )

    result = service.resolve_preview_for_reference(source_kind="post", source_id=303)

    assert result.state is DanbooruImagePreviewState.READY
    assert result.local_path is not None
    assert result.local_path.read_bytes() == b"general-image-bytes"

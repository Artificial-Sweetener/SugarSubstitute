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

"""Unit tests for the Danbooru HTTP client."""

from __future__ import annotations

import requests

from substitute.domain.danbooru import DanbooruLookupStatus
from substitute.infrastructure.external import DanbooruClient


class _FakeResponse:
    """Provide the small response surface used by the Danbooru client."""

    def __init__(
        self,
        payload: object,
        *,
        status_code: int = 200,
        request_error: Exception | None = None,
        content: bytes | None = None,
    ) -> None:
        """Store the payload and optional request failure."""

        self._payload = payload
        self.status_code = status_code
        self._request_error = request_error
        self.content = b"" if content is None else content

    def raise_for_status(self) -> None:
        """Raise the configured request failure when present."""

        if self._request_error is not None:
            raise self._request_error

    def json(self) -> object:
        """Return the configured payload."""

        return self._payload


def test_danbooru_client_parses_post_id_md5_wiki_tag_and_asset_routes() -> None:
    """Danbooru client should parse the supported lookup payloads."""

    calls: list[tuple[str, dict[str, object]]] = []

    def fake_get(url: str, **kwargs: object) -> _FakeResponse:
        """Return route-specific fake Danbooru payloads."""

        calls.append((url, dict(kwargs)))
        if url.endswith("/posts/123.json"):
            return _FakeResponse(_post_payload())
        if url.endswith("/posts.json?md5=abc123def456"):
            return _FakeResponse(_post_payload())
        if url.endswith("/wiki_pages/long%20hair.json"):
            return _FakeResponse(_wiki_payload())
        if url.endswith("/media_assets/37448022.json"):
            return _FakeResponse(_media_asset_payload())
        if url.endswith("/tags.json?search[name]=long%20hair&limit=1"):
            return _FakeResponse([_tag_payload()])
        if url.endswith(
            "/posts.json?tags=head_tilt&limit=2&only=id,created_at,updated_at,"
            "source,md5,rating,tag_string,tag_string_general,tag_string_artist,"
            "tag_string_copyright,tag_string_character,tag_string_meta,file_url,"
            "large_file_url,preview_file_url"
        ):
            return _FakeResponse(
                [_post_payload(post_id=900), _post_payload(post_id=899)]
            )
        raise AssertionError(f"unexpected GET {url}")

    client = DanbooruClient(http_get=fake_get, timeout_seconds=9.0)

    post_by_id = client.get_post_by_id(123)
    post_by_md5 = client.get_post_by_md5("abc123def456")
    wiki_page = client.get_wiki_page("long hair")
    media_asset = client.get_media_asset_by_id(37448022)
    tag = client.get_tag_by_name("long hair")
    recent_posts = client.list_posts_by_tag("head_tilt", limit=2)

    assert post_by_id.status is DanbooruLookupStatus.FOUND
    assert post_by_id.post is not None
    assert post_by_id.post.post_id == 123
    assert post_by_id.post.created_at == "2026-05-01T10:00:00.000-04:00"
    assert post_by_id.post.updated_at == "2026-05-13T12:30:00.000-04:00"
    assert post_by_id.post.rating == "s"
    assert post_by_id.post.tag_string_general == "long_hair smile"
    assert post_by_md5.status is DanbooruLookupStatus.FOUND
    assert post_by_md5.post is not None
    assert post_by_md5.post.md5 == "abc123def456"
    assert wiki_page.status is DanbooruLookupStatus.FOUND
    assert wiki_page.wiki_page is not None
    assert wiki_page.wiki_page.title == "long_hair"
    assert wiki_page.wiki_page.updated_at == "2026-04-19T14:10:46.625-04:00"
    assert wiki_page.wiki_page.other_names == ("long locks",)
    assert media_asset.status is DanbooruLookupStatus.FOUND
    assert media_asset.media_asset is not None
    assert media_asset.media_asset.asset_id == 37448022
    assert media_asset.media_asset.variants[1].variant_type == "360x360"
    assert media_asset.media_asset.variants[1].url == (
        "https://cdn.donmai.us/360x360/c7/ee/c7eedd90ff57e6741953cc32ed34e95a.jpg"
    )
    assert media_asset.media_asset.variants[1].width == 360
    assert media_asset.media_asset.variants[1].height == 203
    assert media_asset.media_asset.image_width == 1280
    assert tag.status is DanbooruLookupStatus.FOUND
    assert tag.tag is not None
    assert tag.tag.name == "long_hair"
    assert tag.tag.updated_at == "2019-08-26T20:40:54.525-04:00"
    assert tag.tag.post_count == 5786558
    assert tuple(post.post_id for post in recent_posts) == (900, 899)

    assert calls == [
        (
            "https://danbooru.donmai.us/posts/123.json",
            {
                "headers": {
                    "Accept": "application/json",
                    "User-Agent": "SugarSubstitute/1.0",
                },
                "timeout": 9.0,
            },
        ),
        (
            "https://danbooru.donmai.us/posts.json?md5=abc123def456",
            {
                "headers": {
                    "Accept": "application/json",
                    "User-Agent": "SugarSubstitute/1.0",
                },
                "timeout": 9.0,
            },
        ),
        (
            "https://danbooru.donmai.us/wiki_pages/long%20hair.json",
            {
                "headers": {
                    "Accept": "application/json",
                    "User-Agent": "SugarSubstitute/1.0",
                },
                "timeout": 9.0,
            },
        ),
        (
            "https://danbooru.donmai.us/media_assets/37448022.json",
            {
                "headers": {
                    "Accept": "application/json",
                    "User-Agent": "SugarSubstitute/1.0",
                },
                "timeout": 9.0,
            },
        ),
        (
            "https://danbooru.donmai.us/tags.json?search[name]=long%20hair&limit=1",
            {
                "headers": {
                    "Accept": "application/json",
                    "User-Agent": "SugarSubstitute/1.0",
                },
                "timeout": 9.0,
            },
        ),
        (
            "https://danbooru.donmai.us/posts.json?tags=head_tilt&limit=2&only=id,created_at,updated_at,source,md5,rating,tag_string,tag_string_general,tag_string_artist,tag_string_copyright,tag_string_character,tag_string_meta,file_url,large_file_url,preview_file_url",
            {
                "headers": {
                    "Accept": "application/json",
                    "User-Agent": "SugarSubstitute/1.0",
                },
                "timeout": 9.0,
            },
        ),
    ]


def test_danbooru_client_maps_not_found_responses() -> None:
    """Danbooru client should convert 404s into typed not-found results."""

    def fake_get(_url: str, **_kwargs: object) -> _FakeResponse:
        """Return one not-found response."""

        return _FakeResponse({}, status_code=404)

    client = DanbooruClient(http_get=fake_get)

    post_result = client.get_post_by_id(999)
    wiki_result = client.get_wiki_page("missing page")
    tag_result = client.get_tag_by_name("missing tag")

    assert post_result.status is DanbooruLookupStatus.NOT_FOUND
    assert wiki_result.status is DanbooruLookupStatus.NOT_FOUND
    assert tag_result.status is DanbooruLookupStatus.NOT_FOUND


def test_danbooru_client_reports_request_failures_as_unavailable() -> None:
    """Danbooru client should convert request exceptions into unavailable results."""

    def fake_get(url: str, **_kwargs: object) -> _FakeResponse:
        """Raise a request exception on status validation."""

        return _FakeResponse(
            {},
            request_error=requests.RequestException(f"offline for {url}"),
        )

    client = DanbooruClient(http_get=fake_get)

    result = client.get_post_by_id(1)

    assert result.status is DanbooruLookupStatus.UNAVAILABLE
    assert "offline" in result.error


def test_danbooru_client_downloads_preview_bytes() -> None:
    """Danbooru client should return raw bytes for preview image downloads."""

    calls: list[tuple[str, dict[str, object]]] = []

    def fake_get(url: str, **kwargs: object) -> _FakeResponse:
        """Return one image payload response."""

        calls.append((url, dict(kwargs)))
        return _FakeResponse({}, content=b"image-bytes")

    client = DanbooruClient(http_get=fake_get, timeout_seconds=9.0)

    result = client.download_binary("https://cdn.donmai.us/180x180/example.jpg")

    assert result == b"image-bytes"
    assert calls == [
        (
            "https://cdn.donmai.us/180x180/example.jpg",
            {
                "headers": {
                    "User-Agent": "SugarSubstitute/1.0",
                },
                "timeout": 9.0,
            },
        )
    ]


def test_danbooru_client_reports_invalid_payload_shapes() -> None:
    """Danbooru client should reject JSON payloads with unexpected shapes."""

    def fake_get(url: str, **_kwargs: object) -> _FakeResponse:
        """Return invalid JSON shapes for different routes."""

        if url.endswith("/posts/1.json"):
            return _FakeResponse(["bad"])
        if url.endswith("/wiki_pages/test.json"):
            return _FakeResponse({"id": 1, "title": "test", "body": 3})
        if url.endswith("/tags.json?search[name]=test&limit=1"):
            return _FakeResponse([{"id": 1, "name": "test"}])
        raise AssertionError(f"unexpected GET {url}")

    client = DanbooruClient(http_get=fake_get)

    post_result = client.get_post_by_id(1)
    wiki_result = client.get_wiki_page("test")
    tag_result = client.get_tag_by_name("test")

    assert post_result.status is DanbooruLookupStatus.INVALID_RESPONSE
    assert wiki_result.status is DanbooruLookupStatus.INVALID_RESPONSE
    assert tag_result.status is DanbooruLookupStatus.INVALID_RESPONSE


def _post_payload(*, post_id: int = 123) -> dict[str, object]:
    """Return a representative Danbooru post payload."""

    return {
        "id": post_id,
        "created_at": "2026-05-01T10:00:00.000-04:00",
        "updated_at": "2026-05-13T12:30:00.000-04:00",
        "source": "https://artist.example/post/123",
        "md5": "abc123def456",
        "rating": "s",
        "tag_string": "long_hair smile commentary",
        "tag_string_general": "long_hair smile",
        "tag_string_artist": "artist_name",
        "tag_string_copyright": "series_name",
        "tag_string_character": "heroine",
        "tag_string_meta": "commentary",
        "file_url": "https://cdn.donmai.us/original/ab/cd/abc123def456.jpg",
        "large_file_url": "https://cdn.donmai.us/sample/ab/cd/abc123def456.jpg",
        "preview_file_url": "https://cdn.donmai.us/180x180/ab/cd/abc123def456.jpg",
    }


def _wiki_payload() -> dict[str, object]:
    """Return a representative Danbooru wiki payload."""

    return {
        "id": 456,
        "created_at": "2008-03-29T11:38:25.828-04:00",
        "updated_at": "2026-04-19T14:10:46.625-04:00",
        "title": "long_hair",
        "body": "h4. Definition\n\nHair that extends below the shoulders.",
        "other_names": ["long locks"],
        "category_name": "general",
    }


def _tag_payload() -> dict[str, object]:
    """Return a representative Danbooru tag payload."""

    return {
        "id": 789,
        "created_at": "2013-02-28T00:04:36.440-05:00",
        "updated_at": "2019-08-26T20:40:54.525-04:00",
        "name": "long_hair",
        "category": 0,
        "post_count": 5786558,
        "is_deprecated": False,
    }


def _media_asset_payload() -> dict[str, object]:
    """Return a representative Danbooru media asset payload."""

    return {
        "id": 37448022,
        "created_at": "2025-11-21T20:45:36.958-05:00",
        "updated_at": "2025-11-21T20:45:38.328-05:00",
        "md5": "c7eedd90ff57e6741953cc32ed34e95a",
        "file_ext": "jpg",
        "image_width": 1280,
        "image_height": 720,
        "variants": [
            {
                "type": "180x180",
                "url": "https://cdn.donmai.us/180x180/c7/ee/c7eedd90ff57e6741953cc32ed34e95a.jpg",
                "width": 180,
                "height": 101,
                "file_ext": "jpg",
            },
            {
                "type": "360x360",
                "url": "https://cdn.donmai.us/360x360/c7/ee/c7eedd90ff57e6741953cc32ed34e95a.jpg",
                "width": 360,
                "height": 203,
                "file_ext": "jpg",
            },
            {
                "type": "720x720",
                "url": "https://cdn.donmai.us/720x720/c7/ee/c7eedd90ff57e6741953cc32ed34e95a.webp",
                "width": 720,
                "height": 405,
                "file_ext": "webp",
            },
            {
                "type": "sample",
                "url": "https://cdn.donmai.us/sample/c7/ee/sample-c7eedd90ff57e6741953cc32ed34e95a.jpg",
                "width": 850,
                "height": 478,
                "file_ext": "jpg",
            },
            {
                "type": "original",
                "url": "https://cdn.donmai.us/original/c7/ee/c7eedd90ff57e6741953cc32ed34e95a.jpg",
                "width": 1280,
                "height": 720,
                "file_ext": "jpg",
            },
        ],
    }

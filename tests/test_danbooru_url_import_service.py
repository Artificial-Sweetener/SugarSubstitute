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

"""Unit tests for Danbooru URL import classification and prompt shaping."""

from __future__ import annotations

from substitute.application.danbooru import (
    DanbooruFailureReason,
    DanbooruUrlImportService,
    DanbooruUrlKind,
)
from substitute.domain.danbooru import (
    DanbooruLookupStatus,
    DanbooruPostLookupResult,
    DanbooruPostRecord,
)


class _StubDanbooruClient:
    """Provide deterministic Danbooru post lookups for URL import tests."""

    def __init__(
        self,
        *,
        post_by_id: DanbooruPostLookupResult | None = None,
        post_by_md5: DanbooruPostLookupResult | None = None,
    ) -> None:
        """Store deterministic provider results and capture lookup calls."""

        self._post_by_id = post_by_id or DanbooruPostLookupResult(
            status=DanbooruLookupStatus.NOT_FOUND
        )
        self._post_by_md5 = post_by_md5 or DanbooruPostLookupResult(
            status=DanbooruLookupStatus.NOT_FOUND
        )
        self.calls: list[tuple[str, object]] = []

    def get_post_by_id(self, post_id: int) -> DanbooruPostLookupResult:
        """Return the configured post-by-id lookup result."""

        self.calls.append(("post_id", post_id))
        return self._post_by_id

    def get_post_by_md5(self, md5: str) -> DanbooruPostLookupResult:
        """Return the configured post-by-md5 lookup result."""

        self.calls.append(("post_md5", md5))
        return self._post_by_md5


def test_danbooru_url_import_service_parses_post_urls_and_formats_prompt_text() -> None:
    """Post URLs should resolve to prompt-safe comma-separated tag text."""

    client = _StubDanbooruClient(
        post_by_id=DanbooruPostLookupResult(
            status=DanbooruLookupStatus.FOUND,
            post=_post_record(),
        )
    )
    service = DanbooruUrlImportService(client=client)

    result = service.import_prompt_from_url(
        "https://danbooru.donmai.us/posts/12345?pool_id=6"
    )

    assert result.succeeded is True
    assert result.classification is not None
    assert result.classification.kind is DanbooruUrlKind.POST
    assert result.imported_prompt is not None
    assert result.imported_prompt.source_post_id == 12345
    assert result.imported_prompt.included_tags == (
        "1girl",
        "long_hair",
        "smile",
        "artist_name",
        "fate/grand_order",
        "saber_(fate)",
    )
    assert result.imported_prompt.excluded_tags == ("commentary", "translation_request")
    assert (
        result.imported_prompt.display_text
        == "1girl, long hair, smile, artist name, fate/grand order, saber \\(fate\\)"
    )
    assert client.calls == [("post_id", 12345)]


def test_danbooru_url_import_service_parses_cdn_urls_by_md5() -> None:
    """CDN image URLs should resolve through the MD5 lookup path."""

    client = _StubDanbooruClient(
        post_by_md5=DanbooruPostLookupResult(
            status=DanbooruLookupStatus.FOUND,
            post=_post_record(post_id=555),
        )
    )
    service = DanbooruUrlImportService(client=client)

    result = service.import_prompt_from_url(
        "https://cdn.donmai.us/sample/sample-0123456789abcdef0123456789abcdef.jpg"
    )

    assert result.succeeded is True
    assert result.classification is not None
    assert result.classification.kind is DanbooruUrlKind.CDN
    assert result.classification.lookup_value == "0123456789abcdef0123456789abcdef"
    assert client.calls == [("post_md5", "0123456789abcdef0123456789abcdef")]


def test_danbooru_url_import_service_rejects_unsupported_urls() -> None:
    """Unsupported URLs should fail with the dedicated unsupported-url reason."""

    service = DanbooruUrlImportService(client=_StubDanbooruClient())

    result = service.import_prompt_from_url("https://example.com/posts/12345")

    assert result.succeeded is False
    assert result.failure_reason is DanbooruFailureReason.UNSUPPORTED_URL
    assert result.classification is None


def test_danbooru_url_import_service_maps_lookup_failures() -> None:
    """Provider failures should surface typed reasons for the paste path."""

    client = _StubDanbooruClient(
        post_by_id=DanbooruPostLookupResult(
            status=DanbooruLookupStatus.UNAVAILABLE,
            error="timed out",
        )
    )
    service = DanbooruUrlImportService(client=client)

    result = service.import_prompt_from_url("https://danbooru.donmai.us/posts/77")

    assert result.succeeded is False
    assert result.failure_reason is DanbooruFailureReason.UNAVAILABLE
    assert result.error == "timed out"


def _post_record(*, post_id: int = 12345) -> DanbooruPostRecord:
    """Return a representative Danbooru post used by URL import tests."""

    return DanbooruPostRecord(
        post_id=post_id,
        created_at="2026-05-01T10:00:00.000-04:00",
        updated_at="2026-05-13T12:30:00.000-04:00",
        source="https://artist.example/posts/12345",
        md5="0123456789abcdef0123456789abcdef",
        rating="s",
        tag_string=(
            "1girl long_hair smile artist_name "
            "fate/grand_order saber_(fate) commentary translation_request"
        ),
        tag_string_general="1girl long_hair smile",
        tag_string_artist="artist_name",
        tag_string_copyright="fate/grand_order",
        tag_string_character="saber_(fate)",
        tag_string_meta="commentary translation_request",
        file_url=(
            "https://cdn.donmai.us/original/01/23/0123456789abcdef0123456789abcdef.jpg"
        ),
        large_file_url=(
            "https://cdn.donmai.us/sample/sample-0123456789abcdef0123456789abcdef.jpg"
        ),
        preview_file_url=(
            "https://cdn.donmai.us/180x180/01/23/0123456789abcdef0123456789abcdef.jpg"
        ),
    )

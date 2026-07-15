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

"""Unit tests for Danbooru wiki lookup normalization and shaping."""

from __future__ import annotations

from substitute.application.danbooru import (
    DanbooruFailureReason,
    DanbooruWikiService,
)
from substitute.domain.danbooru import (
    DanbooruLookupStatus,
    DanbooruTagLookupResult,
    DanbooruTagRecord,
    DanbooruWikiPageLookupResult,
    DanbooruWikiPageRecord,
)


class _StubDanbooruClient:
    """Provide deterministic Danbooru wiki and tag lookup results for tests."""

    def __init__(
        self,
        *,
        wiki_results_by_title: dict[str, DanbooruWikiPageLookupResult],
        tag_results_by_name: dict[str, DanbooruTagLookupResult] | None = None,
    ) -> None:
        """Store deterministic lookup results and capture each requested title."""

        self._wiki_results_by_title = dict(wiki_results_by_title)
        self._tag_results_by_name = dict(tag_results_by_name or {})
        self.calls: list[tuple[str, str]] = []

    def get_wiki_page(self, title: str) -> DanbooruWikiPageLookupResult:
        """Return the configured wiki result for the requested title."""

        self.calls.append(("wiki", title))
        return self._wiki_results_by_title.get(
            title,
            DanbooruWikiPageLookupResult(status=DanbooruLookupStatus.NOT_FOUND),
        )

    def get_tag_by_name(self, name: str) -> DanbooruTagLookupResult:
        """Return the configured tag result for the requested name."""

        self.calls.append(("tag", name))
        return self._tag_results_by_name.get(
            name,
            DanbooruTagLookupResult(status=DanbooruLookupStatus.NOT_FOUND),
        )


def test_danbooru_wiki_service_normalizes_selection_and_builds_page_view() -> None:
    """Selection text should normalize to canonical titles and enrich metadata."""

    client = _StubDanbooruClient(
        wiki_results_by_title={
            "saber_(fate)": DanbooruWikiPageLookupResult(
                status=DanbooruLookupStatus.FOUND,
                wiki_page=_wiki_page_record(),
            )
        },
        tag_results_by_name={
            "saber_(fate)": DanbooruTagLookupResult(
                status=DanbooruLookupStatus.FOUND,
                tag=_tag_record(),
            )
        },
    )
    service = DanbooruWikiService(client=client)

    result = service.lookup_selection(r"  saber \(fate\)  ")

    assert result.succeeded is True
    assert result.page_view is not None
    assert result.navigation_entry is not None
    assert result.resolved_title == "saber_(fate)"
    assert result.page_view.display_title == "saber (fate)"
    assert result.page_view.category_name == "character"
    assert result.page_view.post_count == 124500
    assert result.page_view.other_names == ("artoria pendragon", "king of knights")
    assert result.page_view.canonical_url == (
        "https://danbooru.donmai.us/wiki_pages/saber_%28fate%29"
    )
    assert client.calls == [("wiki", "saber_(fate)"), ("tag", "saber_(fate)")]


def test_danbooru_wiki_service_tries_space_candidate_after_underscore_miss() -> None:
    """Lookup should retry the normalized spaced title when needed."""

    client = _StubDanbooruClient(
        wiki_results_by_title={
            "fgo": DanbooruWikiPageLookupResult(status=DanbooruLookupStatus.NOT_FOUND),
            "fgo alias": DanbooruWikiPageLookupResult(
                status=DanbooruLookupStatus.FOUND,
                wiki_page=_wiki_page_record(title="fgo alias", other_names=()),
            ),
        }
    )
    service = DanbooruWikiService(client=client)

    result = service.lookup_selection("fgo alias")

    assert result.succeeded is True
    assert result.page_view is not None
    assert result.page_view.title == "fgo alias"
    assert client.calls[:2] == [("wiki", "fgo_alias"), ("wiki", "fgo alias")]


def test_danbooru_wiki_service_reports_not_found_after_all_candidates_fail() -> None:
    """Missing pages should return a typed not-found result."""

    service = DanbooruWikiService(client=_StubDanbooruClient(wiki_results_by_title={}))

    result = service.lookup_selection("missing tag")

    assert result.succeeded is False
    assert result.failure_reason is DanbooruFailureReason.NOT_FOUND
    assert result.resolved_title == "missing_tag"


def test_danbooru_wiki_service_reports_empty_selection() -> None:
    """Blank selections should fail before any provider lookup is attempted."""

    client = _StubDanbooruClient(wiki_results_by_title={})
    service = DanbooruWikiService(client=client)

    result = service.lookup_selection("   ,  ")

    assert result.succeeded is False
    assert result.failure_reason is DanbooruFailureReason.EMPTY_INPUT
    assert client.calls == []


def _wiki_page_record(
    *,
    title: str = "saber_(fate)",
    other_names: tuple[str, ...] = ("artoria_pendragon", "king_of_knights"),
) -> DanbooruWikiPageRecord:
    """Return a representative Danbooru wiki page record."""

    return DanbooruWikiPageRecord(
        wiki_page_id=10,
        created_at="2008-03-29T11:38:25.828-04:00",
        updated_at="2026-04-19T14:10:46.625-04:00",
        title=title,
        body="h4. Definition\n\nKing Arthur in the Fate series.",
        other_names=other_names,
        category_name=None,
    )


def _tag_record() -> DanbooruTagRecord:
    """Return a representative Danbooru tag metadata record."""

    return DanbooruTagRecord(
        tag_id=11,
        created_at="2013-02-28T00:04:36.440-05:00",
        updated_at="2019-08-26T20:40:54.525-04:00",
        name="saber_(fate)",
        category=4,
        post_count=124500,
        is_deprecated=False,
    )

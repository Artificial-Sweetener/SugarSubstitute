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

"""Unit tests for cached Danbooru wiki content retrieval."""

from __future__ import annotations

from pathlib import Path

from tests.execution_testing import ImmediateTaskSubmitter
from substitute.application.danbooru import DanbooruFailureReason
from substitute.application.danbooru.content_models import (
    DanbooruContentFreshnessState,
)
from substitute.application.danbooru.preferences_service import (
    DanbooruPreferenceService,
)
from substitute.application.danbooru.wiki_content_service import (
    DanbooruWikiContentService,
)
from substitute.application.danbooru.wiki_inline_resolution_service import (
    DanbooruWikiInlineResolutionService,
)
from substitute.domain.danbooru import (
    DanbooruCachedWikiPage,
    DanbooruLookupStatus,
    DanbooruTagLookupResult,
    DanbooruTagRecord,
    DanbooruWikiPageLookupResult,
    DanbooruWikiPageRecord,
)
from substitute.infrastructure.persistence.danbooru_cache_store import (
    SqliteDanbooruCacheStore,
)


class _StubDanbooruWikiContentClient:
    """Provide deterministic wiki and tag lookup results for cache tests."""

    def __init__(
        self,
        *,
        wiki_results_by_title: dict[str, DanbooruWikiPageLookupResult],
        tag_results_by_name: dict[str, DanbooruTagLookupResult] | None = None,
    ) -> None:
        """Store deterministic lookup results and capture each call."""

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
        """Return the configured tag result for the requested title."""

        self.calls.append(("tag", name))
        return self._tag_results_by_name.get(
            name,
            DanbooruTagLookupResult(status=DanbooruLookupStatus.NOT_FOUND),
        )


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


def test_wiki_content_service_uses_cache_after_first_lookup(tmp_path: Path) -> None:
    """Repeated wiki lookups should reuse the cached page and tag metadata."""

    client = _StubDanbooruWikiContentClient(
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
    service = _service(tmp_path, client=client)

    first = service.lookup_title("saber_(fate)")
    second = service.lookup_title("saber_(fate)")

    assert first.succeeded is True
    assert second.succeeded is True
    assert first.page == second.page
    assert client.calls == [("wiki", "saber_(fate)"), ("tag", "saber_(fate)")]


def test_wiki_content_service_returns_stale_cache_and_refreshes_in_background(
    tmp_path: Path,
) -> None:
    """Stale cached wiki content should render immediately and refresh later."""

    store = SqliteDanbooruCacheStore(tmp_path)
    store.save_cached_wiki_page(
        DanbooruCachedWikiPage(
            title="saber_(fate)",
            lookup_status=DanbooruLookupStatus.FOUND,
            wiki_page=_wiki_page_record(body="Old body."),
            fetched_at="2026-05-01T10:00:00+00:00",
            expires_at="2026-05-02T10:00:00+00:00",
        )
    )
    client = _StubDanbooruWikiContentClient(
        wiki_results_by_title={
            "saber_(fate)": DanbooruWikiPageLookupResult(
                status=DanbooruLookupStatus.FOUND,
                wiki_page=_wiki_page_record(body="New body."),
            )
        },
        tag_results_by_name={
            "saber_(fate)": DanbooruTagLookupResult(
                status=DanbooruLookupStatus.FOUND,
                tag=_tag_record(),
            )
        },
    )
    service = _service(tmp_path, client=client)

    result = service.lookup_title("saber_(fate)")

    assert result.page is not None
    assert result.page.body_dtext == "Old body."
    assert result.page.freshness_state is DanbooruContentFreshnessState.STALE
    refreshed = store.load_cached_wiki_page("saber_(fate)")
    assert refreshed is not None
    assert refreshed.wiki_page is not None
    assert refreshed.wiki_page.body == "New body."


def test_wiki_content_service_negative_caches_missing_pages(tmp_path: Path) -> None:
    """Missing pages should be stored so repeated lookups avoid extra API calls."""

    client = _StubDanbooruWikiContentClient(wiki_results_by_title={})
    service = _service(tmp_path, client=client)

    first = service.lookup_title("missing_tag")
    second = service.lookup_title("missing_tag")

    assert first.succeeded is False
    assert first.failure_reason is DanbooruFailureReason.NOT_FOUND
    assert second.succeeded is False
    assert second.failure_reason is DanbooruFailureReason.NOT_FOUND
    assert client.calls == [("wiki", "missing_tag")]


def test_wiki_content_service_preserves_url_shaped_aliases(tmp_path: Path) -> None:
    """URL aliases should survive display shaping without underscore normalization."""

    client = _StubDanbooruWikiContentClient(
        wiki_results_by_title={
            "artist_name": DanbooruWikiPageLookupResult(
                status=DanbooruLookupStatus.FOUND,
                wiki_page=_wiki_page_record(
                    title="artist_name",
                    other_names=("pixiv #12345678", "https://www.pixiv.net/users/2468"),
                ),
            )
        }
    )
    service = _service(tmp_path, client=client)

    result = service.lookup_title("artist_name")

    assert result.page is not None
    assert result.page.other_names == (
        "pixiv #12345678",
        "https://www.pixiv.net/users/2468",
    )


def _service(
    tmp_path: Path,
    *,
    client: _StubDanbooruWikiContentClient,
) -> DanbooruWikiContentService:
    """Create one cached wiki content service for tests."""

    preference_service = DanbooruPreferenceService(
        _MemoryDanbooruPreferenceRepository()
    )
    cache_repository = SqliteDanbooruCacheStore(tmp_path)
    return DanbooruWikiContentService(
        client=client,
        cache_repository=cache_repository,
        preference_service=preference_service,
        inline_resolution_service=DanbooruWikiInlineResolutionService(
            cache_repository=cache_repository,
        ),
        refresh_submitter=ImmediateTaskSubmitter(),
    )


def _wiki_page_record(
    *,
    title: str = "saber_(fate)",
    body: str = "h4. Definition\n\nKing Arthur in the Fate series.",
    other_names: tuple[str, ...] = ("artoria_pendragon",),
) -> DanbooruWikiPageRecord:
    """Return one representative Danbooru wiki page record."""

    return DanbooruWikiPageRecord(
        wiki_page_id=10,
        created_at="2008-03-29T11:38:25.828-04:00",
        updated_at="2026-04-19T14:10:46.625-04:00",
        title=title,
        body=body,
        other_names=other_names,
        category_name=None,
    )


def _tag_record() -> DanbooruTagRecord:
    """Return one representative Danbooru tag metadata record."""

    return DanbooruTagRecord(
        tag_id=11,
        created_at="2013-02-28T00:04:36.440-05:00",
        updated_at="2019-08-26T20:40:54.525-04:00",
        name="saber_(fate)",
        category=4,
        post_count=124500,
        is_deprecated=False,
    )

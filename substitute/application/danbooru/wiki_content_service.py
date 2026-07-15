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

"""Load Danbooru wiki content through the persistent cache layer."""

from __future__ import annotations

from collections.abc import Callable
from itertools import count
from typing import Protocol
from urllib.parse import quote

from substitute.application.execution import (
    ExecutionContext,
    ScopedKeyedSingleFlight,
    TaskIdentity,
    TaskRequest,
    TaskSubmitter,
)
from substitute.application.danbooru.cache_policy import (
    NEGATIVE_LOOKUP_CACHE_TTL,
    TAG_CACHE_TTL,
    WIKI_PAGE_CACHE_TTL,
    current_utc_timestamp,
    expires_at_text,
    timestamp_is_expired,
)
from substitute.application.danbooru.content_models import (
    DanbooruContentFreshnessState,
    DanbooruWikiContentLookupResult,
    DanbooruWikiContentPage,
)
from substitute.application.danbooru.wiki_inline_resolution_service import (
    DanbooruWikiInlineResolutionService,
)
from substitute.application.danbooru.wiki_render_models import (
    DanbooruWikiSectionContent,
)
from substitute.application.danbooru.dtext_normalization import (
    candidate_titles_for_selection,
    prompt_display_text_from_alias,
    prompt_display_text_from_tag,
)
from substitute.application.danbooru.models import (
    DanbooruFailureReason,
    DanbooruWikiNavigationEntry,
)
from substitute.application.danbooru.preferences_service import (
    DanbooruPreferenceService,
)
from substitute.application.ports.danbooru_cache_repository import (
    DanbooruCacheRepository,
)
from substitute.domain.danbooru import (
    DanbooruCachedTag,
    DanbooruCachedWikiPage,
    DanbooruLookupStatus,
    DanbooruTagLookupResult,
    DanbooruTagRecord,
    DanbooruWikiPageLookupResult,
    DanbooruWikiPageRecord,
)
from substitute.shared.logging.logger import get_logger, log_debug, log_warning

_LOGGER = get_logger("application.danbooru.wiki_content_service")
_CATEGORY_NAMES = {
    0: "general",
    1: "artist",
    3: "copyright",
    4: "character",
    5: "meta",
}
_WIKI_BASE_URL = "https://danbooru.donmai.us/wiki_pages"


class DanbooruWikiContentClient(Protocol):
    """Describe the client surface needed for cached wiki content retrieval."""

    def get_wiki_page(self, title: str) -> DanbooruWikiPageLookupResult:
        """Return one wiki-page lookup result for the supplied title."""

    def get_tag_by_name(self, name: str) -> DanbooruTagLookupResult:
        """Return one tag metadata lookup result for the supplied name."""


class DanbooruWikiContentService:
    """Serve Danbooru wiki content from cache with lazy per-entity refresh."""

    def __init__(
        self,
        *,
        client: DanbooruWikiContentClient,
        cache_repository: DanbooruCacheRepository,
        preference_service: DanbooruPreferenceService,
        inline_resolution_service: DanbooruWikiInlineResolutionService,
        refresh_submitter: TaskSubmitter,
    ) -> None:
        """Store the collaborators used for cached wiki retrieval."""

        self._client = client
        self._cache_repository = cache_repository
        self._preference_service = preference_service
        self._inline_resolution_service = inline_resolution_service
        self._refresh_request_ids = count(1)
        self._refresh_single_flight: ScopedKeyedSingleFlight[tuple[str, str], None] = (
            ScopedKeyedSingleFlight(submitter=refresh_submitter)
        )

    def shutdown(self) -> None:
        """Cancel active background refreshes owned by this service."""

        self._refresh_single_flight.cancel_all(reason="danbooru_wiki_service_shutdown")

    def lookup_selection(self, selection_text: str) -> DanbooruWikiContentLookupResult:
        """Resolve one selected prompt fragment into cached wiki content."""

        candidate_titles = candidate_titles_for_selection(selection_text)
        if not candidate_titles:
            return DanbooruWikiContentLookupResult(
                page=None,
                navigation_entry=None,
                requested_text=selection_text,
                failure_reason=DanbooruFailureReason.EMPTY_INPUT,
            )
        return self._lookup_candidates(
            requested_text=selection_text,
            candidate_titles=candidate_titles,
        )

    def lookup_title(self, title: str) -> DanbooruWikiContentLookupResult:
        """Resolve one explicit Danbooru title into cached wiki content."""

        stripped = title.strip()
        if not stripped:
            return DanbooruWikiContentLookupResult(
                page=None,
                navigation_entry=None,
                requested_text=title,
                failure_reason=DanbooruFailureReason.EMPTY_INPUT,
            )
        return self._lookup_candidates(
            requested_text=title,
            candidate_titles=(stripped,),
        )

    def resolve_sections(
        self,
        sections: tuple[DanbooruWikiSectionContent, ...],
    ) -> tuple[DanbooruWikiSectionContent, ...]:
        """Resolve parsed section content into title-shaped tag chips."""

        return self._inline_resolution_service.resolve_sections(sections)

    def _lookup_candidates(
        self,
        *,
        requested_text: str,
        candidate_titles: tuple[str, ...],
    ) -> DanbooruWikiContentLookupResult:
        """Resolve one ordered set of candidate titles into cached wiki content."""

        log_debug(
            _LOGGER,
            "Danbooru cached wiki lookup requested.",
            requested_text=requested_text,
            candidate_count=len(candidate_titles),
        )
        for candidate_title in candidate_titles:
            cached_entry = self._cache_repository.load_cached_wiki_page(candidate_title)
            if cached_entry is not None:
                cached_result = self._result_from_cached_entry(
                    cached_entry=cached_entry,
                    requested_text=requested_text,
                )
                if cached_result is not None:
                    return cached_result
            fetched = self._fetch_wiki_page(candidate_title)
            if fetched.status is DanbooruLookupStatus.NOT_FOUND:
                continue
            if (
                fetched.status is not DanbooruLookupStatus.FOUND
                or fetched.wiki_page is None
            ):
                return DanbooruWikiContentLookupResult(
                    page=None,
                    navigation_entry=None,
                    requested_text=requested_text,
                    resolved_title=candidate_title,
                    failure_reason=_failure_reason_from_lookup_status(fetched.status),
                    error=fetched.error,
                )
            return self._success_result(
                requested_text=requested_text,
                wiki_page=fetched.wiki_page,
                freshness_state=DanbooruContentFreshnessState.FRESH,
            )
        return DanbooruWikiContentLookupResult(
            page=None,
            navigation_entry=None,
            requested_text=requested_text,
            resolved_title=candidate_titles[0],
            failure_reason=DanbooruFailureReason.NOT_FOUND,
        )

    def _result_from_cached_entry(
        self,
        *,
        cached_entry: DanbooruCachedWikiPage,
        requested_text: str,
    ) -> DanbooruWikiContentLookupResult | None:
        """Build one lookup result from a cached wiki entry when usable."""

        is_stale = timestamp_is_expired(cached_entry.expires_at)
        freshness_state = (
            DanbooruContentFreshnessState.STALE
            if is_stale
            else DanbooruContentFreshnessState.FRESH
        )
        if cached_entry.lookup_status is DanbooruLookupStatus.NOT_FOUND:
            if is_stale:
                self._schedule_wiki_refresh(cached_entry.title)
                return None
            return DanbooruWikiContentLookupResult(
                page=None,
                navigation_entry=None,
                requested_text=requested_text,
                resolved_title=cached_entry.title,
                failure_reason=DanbooruFailureReason.NOT_FOUND,
            )
        if cached_entry.lookup_status is not DanbooruLookupStatus.FOUND:
            if is_stale:
                self._schedule_wiki_refresh(cached_entry.title)
            return DanbooruWikiContentLookupResult(
                page=None,
                navigation_entry=None,
                requested_text=requested_text,
                resolved_title=cached_entry.title,
                failure_reason=_failure_reason_from_lookup_status(
                    cached_entry.lookup_status
                ),
                error=cached_entry.error,
            )
        if cached_entry.wiki_page is None:
            return DanbooruWikiContentLookupResult(
                page=None,
                navigation_entry=None,
                requested_text=requested_text,
                resolved_title=cached_entry.title,
                failure_reason=DanbooruFailureReason.INVALID_RESPONSE,
                error="Cached Danbooru wiki entry was missing page content.",
            )
        if is_stale:
            self._schedule_wiki_refresh(cached_entry.title)
        return self._success_result(
            requested_text=requested_text,
            wiki_page=cached_entry.wiki_page,
            freshness_state=freshness_state,
        )

    def _success_result(
        self,
        *,
        requested_text: str,
        wiki_page: DanbooruWikiPageRecord,
        freshness_state: DanbooruContentFreshnessState,
    ) -> DanbooruWikiContentLookupResult:
        """Build one successful wiki-content lookup result."""

        tag_record, tag_is_stale = self._load_or_fetch_tag(wiki_page.title)
        if tag_is_stale:
            self._schedule_tag_refresh(wiki_page.title)
        page = DanbooruWikiContentPage(
            title=wiki_page.title,
            display_title=prompt_display_text_from_tag(wiki_page.title),
            category_name=wiki_page.category_name
            or _category_name_from_tag(tag_record),
            post_count=None if tag_record is None else tag_record.post_count,
            other_names=tuple(
                prompt_display_text_from_alias(name) for name in wiki_page.other_names
            ),
            canonical_url=f"{_WIKI_BASE_URL}/{quote(wiki_page.title)}",
            body_dtext=wiki_page.body,
            freshness_state=freshness_state,
        )
        return DanbooruWikiContentLookupResult(
            page=page,
            navigation_entry=DanbooruWikiNavigationEntry(
                title=page.title,
                display_title=page.display_title,
            ),
            requested_text=requested_text,
            resolved_title=page.title,
        )

    def _load_or_fetch_tag(self, name: str) -> tuple[DanbooruTagRecord | None, bool]:
        """Return cached tag metadata for one wiki title, fetching when absent."""

        cached_entry = self._cache_repository.load_cached_tag(name)
        if cached_entry is not None:
            is_stale = timestamp_is_expired(cached_entry.expires_at)
            if cached_entry.lookup_status is DanbooruLookupStatus.FOUND:
                return cached_entry.tag, is_stale
            if cached_entry.lookup_status is DanbooruLookupStatus.NOT_FOUND:
                return None, is_stale
        fetched = self._fetch_tag(name)
        if fetched.status is DanbooruLookupStatus.FOUND:
            return fetched.tag, False
        return None, False

    def _fetch_wiki_page(self, title: str) -> DanbooruWikiPageLookupResult:
        """Fetch one wiki page from Danbooru and persist the cache result."""

        result = self._client.get_wiki_page(title)
        now = current_utc_timestamp()
        if result.status is DanbooruLookupStatus.FOUND and result.wiki_page is not None:
            self._cache_repository.save_cached_wiki_page(
                DanbooruCachedWikiPage(
                    title=title,
                    lookup_status=result.status,
                    wiki_page=result.wiki_page,
                    fetched_at=now.isoformat(),
                    expires_at=expires_at_text(WIKI_PAGE_CACHE_TTL, now=now),
                    error=result.error,
                )
            )
        else:
            self._cache_repository.save_cached_wiki_page(
                DanbooruCachedWikiPage(
                    title=title,
                    lookup_status=result.status,
                    wiki_page=None,
                    fetched_at=now.isoformat(),
                    expires_at=expires_at_text(NEGATIVE_LOOKUP_CACHE_TTL, now=now),
                    error=result.error,
                )
            )
        return result

    def _fetch_tag(self, name: str) -> DanbooruTagLookupResult:
        """Fetch one tag record from Danbooru and persist the cache result."""

        result = self._client.get_tag_by_name(name)
        now = current_utc_timestamp()
        self._cache_repository.save_cached_tag(
            DanbooruCachedTag(
                name=name,
                lookup_status=result.status,
                tag=result.tag,
                fetched_at=now.isoformat(),
                expires_at=expires_at_text(
                    TAG_CACHE_TTL
                    if result.status is DanbooruLookupStatus.FOUND
                    else NEGATIVE_LOOKUP_CACHE_TTL,
                    now=now,
                ),
                error=result.error,
            )
        )
        return result

    def _schedule_wiki_refresh(self, title: str) -> None:
        """Schedule a stale wiki page refresh when preferences allow it."""

        if not self._preference_service.load_preferences().background_refresh_enabled:
            return
        self._schedule_refresh(("wiki", title), lambda: self._fetch_wiki_page(title))
        self._schedule_refresh(("tag", title), lambda: self._fetch_tag(title))

    def _schedule_tag_refresh(self, name: str) -> None:
        """Schedule a stale tag refresh when preferences allow it."""

        if not self._preference_service.load_preferences().background_refresh_enabled:
            return
        self._schedule_refresh(("tag", name), lambda: self._fetch_tag(name))

    def _schedule_refresh(
        self,
        cache_key: tuple[str, str],
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
                    "Danbooru background refresh failed.",
                    cache_key=":".join(cache_key),
                    error=repr(error),
                )

        request: TaskRequest[None] = TaskRequest(
            identity=TaskIdentity(
                request_id=next(self._refresh_request_ids),
                domain="danbooru_wiki_refresh",
                parts=(("kind", cache_key[0]), ("key", cache_key[1])),
            ),
            context=ExecutionContext(
                operation="danbooru_wiki_refresh",
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
                "Danbooru background refresh submission failed.",
                cache_key=":".join(cache_key),
                error=repr(error),
            )


def _category_name_from_tag(tag_record: DanbooruTagRecord | None) -> str | None:
    """Return the human-readable category label for one tag record."""

    if tag_record is None:
        return None
    return _CATEGORY_NAMES.get(tag_record.category)


def _failure_reason_from_lookup_status(
    status: DanbooruLookupStatus,
) -> DanbooruFailureReason:
    """Map one provider-layer status to the application wiki failure reason."""

    if status is DanbooruLookupStatus.NOT_FOUND:
        return DanbooruFailureReason.NOT_FOUND
    if status is DanbooruLookupStatus.UNAVAILABLE:
        return DanbooruFailureReason.UNAVAILABLE
    return DanbooruFailureReason.INVALID_RESPONSE


__all__ = ["DanbooruWikiContentClient", "DanbooruWikiContentService"]

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

"""Resolve prompt selections into Danbooru wiki pages and metadata."""

from __future__ import annotations

from typing import Protocol
from urllib.parse import quote

from substitute.application.danbooru.dtext_normalization import (
    candidate_titles_for_selection,
    prompt_display_text_from_alias,
    prompt_display_text_from_tag,
)
from substitute.application.danbooru.models import (
    DanbooruFailureReason,
    DanbooruWikiLookupResult,
    DanbooruWikiNavigationEntry,
    DanbooruWikiPageView,
)
from substitute.domain.danbooru import (
    DanbooruLookupStatus,
    DanbooruTagLookupResult,
    DanbooruTagRecord,
    DanbooruWikiPageLookupResult,
    DanbooruWikiPageRecord,
)
from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger("application.danbooru.wiki_service")
_CATEGORY_NAMES = {
    0: "general",
    1: "artist",
    3: "copyright",
    4: "character",
    5: "meta",
}
_WIKI_BASE_URL = "https://danbooru.donmai.us/wiki_pages"


class DanbooruWikiService:
    """Load Danbooru wiki content and enrich it with tag metadata."""

    def __init__(self, *, client: "DanbooruWikiLookupClient") -> None:
        """Store the Danbooru client used for wiki and tag lookups."""

        self._client = client

    def lookup_selection(self, selection_text: str) -> DanbooruWikiLookupResult:
        """Return one wiki page view for the selected prompt text when available."""

        candidate_titles = candidate_titles_for_selection(selection_text)
        if not candidate_titles:
            return DanbooruWikiLookupResult(
                page_view=None,
                navigation_entry=None,
                requested_text=selection_text,
                failure_reason=DanbooruFailureReason.EMPTY_INPUT,
            )
        return self._lookup_candidates(
            requested_text=selection_text,
            candidate_titles=candidate_titles,
        )

    def lookup_title(self, title: str) -> DanbooruWikiLookupResult:
        """Return one wiki page view for a known wiki title or internal link target."""

        stripped = title.strip()
        if not stripped:
            return DanbooruWikiLookupResult(
                page_view=None,
                navigation_entry=None,
                requested_text=title,
                failure_reason=DanbooruFailureReason.EMPTY_INPUT,
            )
        return self._lookup_candidates(
            requested_text=title,
            candidate_titles=(stripped,),
        )

    def _lookup_candidates(
        self,
        *,
        requested_text: str,
        candidate_titles: tuple[str, ...],
    ) -> DanbooruWikiLookupResult:
        """Resolve one ordered set of candidate titles into a wiki page view."""

        log_debug(
            _LOGGER,
            "Danbooru wiki lookup requested.",
            requested_text=requested_text,
            candidate_count=len(candidate_titles),
        )

        for candidate_title in candidate_titles:
            wiki_result = self._client.get_wiki_page(candidate_title)
            if wiki_result.status is DanbooruLookupStatus.NOT_FOUND:
                continue
            if (
                wiki_result.status is not DanbooruLookupStatus.FOUND
                or wiki_result.wiki_page is None
            ):
                return DanbooruWikiLookupResult(
                    page_view=None,
                    navigation_entry=None,
                    requested_text=requested_text,
                    resolved_title=candidate_title,
                    failure_reason=_failure_reason_from_lookup_status(
                        wiki_result.status
                    ),
                    error=wiki_result.error,
                )

            page_view = self._build_page_view(wiki_result.wiki_page)
            navigation_entry = DanbooruWikiNavigationEntry(
                title=page_view.title,
                display_title=page_view.display_title,
            )
            log_debug(
                _LOGGER,
                "Danbooru wiki lookup resolved page.",
                requested_text=requested_text,
                resolved_title=page_view.title,
                has_tag_metadata=page_view.post_count is not None,
            )
            return DanbooruWikiLookupResult(
                page_view=page_view,
                navigation_entry=navigation_entry,
                requested_text=requested_text,
                resolved_title=page_view.title,
            )

        return DanbooruWikiLookupResult(
            page_view=None,
            navigation_entry=None,
            requested_text=requested_text,
            resolved_title=candidate_titles[0],
            failure_reason=DanbooruFailureReason.NOT_FOUND,
        )

    def _build_page_view(
        self, wiki_page: DanbooruWikiPageRecord
    ) -> DanbooruWikiPageView:
        """Build one application-facing page view from the wiki and tag lookups."""

        tag_result = self._client.get_tag_by_name(wiki_page.title)
        tag_record = (
            tag_result.tag if tag_result.status is DanbooruLookupStatus.FOUND else None
        )
        category_name = wiki_page.category_name or _category_name_from_tag(tag_record)
        post_count = None if tag_record is None else tag_record.post_count
        return DanbooruWikiPageView(
            title=wiki_page.title,
            display_title=prompt_display_text_from_tag(wiki_page.title),
            category_name=category_name,
            post_count=post_count,
            other_names=tuple(
                prompt_display_text_from_alias(name) for name in wiki_page.other_names
            ),
            body_dtext=wiki_page.body,
            canonical_url=f"{_WIKI_BASE_URL}/{quote(wiki_page.title)}",
            exists=True,
        )


def _category_name_from_tag(tag_record: DanbooruTagRecord | None) -> str | None:
    """Return the tag-category label used by the native wiki header."""

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


class DanbooruWikiLookupClient(Protocol):
    """Describe the client surface needed for wiki-page presentation lookups."""

    def get_wiki_page(self, title: str) -> DanbooruWikiPageLookupResult:
        """Return one wiki-page lookup result for the supplied title."""

    def get_tag_by_name(self, name: str) -> DanbooruTagLookupResult:
        """Return one tag metadata lookup result for the supplied tag name."""


__all__ = ["DanbooruWikiService"]

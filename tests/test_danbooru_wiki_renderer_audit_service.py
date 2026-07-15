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

"""Unit tests for cached Danbooru wiki renderer audit scanning."""

from __future__ import annotations

from pathlib import Path

from substitute.application.danbooru import DanbooruWikiRendererAuditService
from substitute.domain.danbooru import (
    DanbooruCachedWikiPage,
    DanbooruLookupStatus,
    DanbooruWikiPageRecord,
)
from substitute.infrastructure.persistence.danbooru_cache_store import (
    SqliteDanbooruCacheStore,
)


def test_wiki_renderer_audit_service_detects_known_quoted_link_patterns(
    tmp_path: Path,
) -> None:
    """The audit service should inventory quoted links found in cached wiki bodies."""

    store = SqliteDanbooruCacheStore(tmp_path)
    store.save_cached_wiki_page(
        DanbooruCachedWikiPage(
            title="serious",
            lookup_status=DanbooruLookupStatus.FOUND,
            wiki_page=_wiki_page_record(
                title="serious",
                body='h4. See also\n\n"Pool: Serious Beauty":/pools/4339',
            ),
            fetched_at="2026-05-14T16:00:00+00:00",
            expires_at="2026-05-21T16:00:00+00:00",
        )
    )
    store.save_cached_wiki_page(
        DanbooruCachedWikiPage(
            title="contrapposto",
            lookup_status=DanbooruLookupStatus.FOUND,
            wiki_page=_wiki_page_record(
                title="contrapposto",
                body=(
                    "h4. See also\n\n"
                    '"Wikipedia: Contrapposto":http://en.wikipedia.org/wiki/Contrapposto'
                ),
            ),
            fetched_at="2026-05-14T16:00:00+00:00",
            expires_at="2026-05-21T16:00:00+00:00",
        )
    )

    report = DanbooruWikiRendererAuditService(store).audit_cached_pages()

    assert report.cached_page_count == 2
    assert len(report.findings) == 2
    assert report.findings[0].pattern_name == "quoted_external_link"
    assert report.findings[0].page_title == "contrapposto"
    assert "Wikipedia: Contrapposto" in report.findings[0].excerpt
    assert report.findings[1].pattern_name == "quoted_relative_danbooru_link"
    assert report.findings[1].page_title == "serious"
    assert "Pool: Serious Beauty" in report.findings[1].excerpt


def test_wiki_renderer_audit_service_ignores_supported_post_embeds(
    tmp_path: Path,
) -> None:
    """The audit service should not report already supported post embed syntax."""

    store = SqliteDanbooruCacheStore(tmp_path)
    store.save_cached_wiki_page(
        DanbooruCachedWikiPage(
            title="center_opening",
            lookup_status=DanbooruLookupStatus.FOUND,
            wiki_page=_wiki_page_record(
                title="center_opening",
                body="h4. Examples\n\n* !post #7722904: [[open clothes|Open]]",
            ),
            fetched_at="2026-05-14T16:00:00+00:00",
            expires_at="2026-05-21T16:00:00+00:00",
        )
    )

    report = DanbooruWikiRendererAuditService(store).audit_cached_pages()

    assert report.cached_page_count == 1
    assert report.findings == ()


def _wiki_page_record(*, title: str, body: str) -> DanbooruWikiPageRecord:
    """Return one representative cached wiki page record for audit tests."""

    return DanbooruWikiPageRecord(
        wiki_page_id=10,
        created_at="2008-03-29T11:38:25.828-04:00",
        updated_at="2026-04-19T14:10:46.625-04:00",
        title=title,
        body=body,
        other_names=(),
        category_name="general",
    )

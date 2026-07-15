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

"""Unit tests for the persistent Danbooru cache store."""

from __future__ import annotations

from pathlib import Path

from substitute.domain.danbooru import (
    DanbooruCachedImageAsset,
    DanbooruCachedPost,
    DanbooruCachedPostSearch,
    DanbooruCachedTag,
    DanbooruCachedWikiPage,
    DanbooruLookupStatus,
    DanbooruPostRecord,
    DanbooruTagRecord,
    DanbooruWikiPageRecord,
)
from substitute.infrastructure.persistence.danbooru_cache_store import (
    SqliteDanbooruCacheStore,
)


def test_danbooru_cache_store_round_trips_metadata_entries(tmp_path: Path) -> None:
    """The Danbooru cache store should persist wiki, tag, and post records."""

    store = SqliteDanbooruCacheStore(tmp_path)
    wiki_entry = DanbooruCachedWikiPage(
        title="long_hair",
        lookup_status=DanbooruLookupStatus.FOUND,
        wiki_page=_wiki_page_record(),
        fetched_at="2026-05-14T16:00:00+00:00",
        expires_at="2026-05-21T16:00:00+00:00",
    )
    tag_entry = DanbooruCachedTag(
        name="long_hair",
        lookup_status=DanbooruLookupStatus.FOUND,
        tag=_tag_record(),
        fetched_at="2026-05-14T16:00:00+00:00",
        expires_at="2026-05-17T16:00:00+00:00",
    )
    post_entry = DanbooruCachedPost(
        post_id=12345,
        lookup_status=DanbooruLookupStatus.FOUND,
        post=_post_record(),
        fetched_at="2026-05-14T16:00:00+00:00",
        expires_at="2026-05-15T16:00:00+00:00",
    )

    store.save_cached_wiki_page(wiki_entry)
    store.save_cached_tag(tag_entry)
    store.save_cached_post(post_entry)
    store.save_cached_post_search(
        DanbooruCachedPostSearch(
            tag_name="long_hair",
            post_ids=(12345, 67890),
            fetched_at="2026-05-14T16:00:00+00:00",
            expires_at="2026-05-14T22:00:00+00:00",
        )
    )

    assert store.load_cached_wiki_page("long_hair") == wiki_entry
    assert store.load_cached_tag("long_hair") == tag_entry
    assert store.load_cached_post(12345) == post_entry
    assert store.load_cached_post_search("long_hair") == DanbooruCachedPostSearch(
        tag_name="long_hair",
        post_ids=(12345, 67890),
        fetched_at="2026-05-14T16:00:00+00:00",
        expires_at="2026-05-14T22:00:00+00:00",
    )


def test_danbooru_cache_store_persists_negative_cache_entries(tmp_path: Path) -> None:
    """The Danbooru cache store should preserve negative lookup results."""

    store = SqliteDanbooruCacheStore(tmp_path)
    missing_wiki = DanbooruCachedWikiPage(
        title="missing_tag",
        lookup_status=DanbooruLookupStatus.NOT_FOUND,
        wiki_page=None,
        fetched_at="2026-05-14T16:00:00+00:00",
        expires_at="2026-05-14T22:00:00+00:00",
        error="",
    )

    store.save_cached_wiki_page(missing_wiki)

    assert store.load_cached_wiki_page("missing_tag") == missing_wiki


def test_danbooru_cache_store_lists_cached_wiki_pages_in_title_order(
    tmp_path: Path,
) -> None:
    """The Danbooru cache store should expose cached wiki pages deterministically."""

    store = SqliteDanbooruCacheStore(tmp_path)
    store.save_cached_wiki_page(
        DanbooruCachedWikiPage(
            title="zebra_print",
            lookup_status=DanbooruLookupStatus.NOT_FOUND,
            wiki_page=None,
            fetched_at="2026-05-14T16:00:00+00:00",
            expires_at="2026-05-14T22:00:00+00:00",
            error="",
        )
    )
    store.save_cached_wiki_page(
        DanbooruCachedWikiPage(
            title="apple_hair",
            lookup_status=DanbooruLookupStatus.FOUND,
            wiki_page=_wiki_page_record(title="apple_hair"),
            fetched_at="2026-05-14T16:00:00+00:00",
            expires_at="2026-05-21T16:00:00+00:00",
        )
    )

    assert tuple(entry.title for entry in store.list_cached_wiki_pages()) == (
        "apple_hair",
        "zebra_print",
    )


def test_danbooru_cache_store_persists_preview_image_assets(tmp_path: Path) -> None:
    """The Danbooru cache store should write preview image bytes and metadata."""

    store = SqliteDanbooruCacheStore(tmp_path)
    asset = DanbooruCachedImageAsset(
        cache_key="preview:12345",
        source_url="https://cdn.donmai.us/180x180/example.jpg",
        local_path=Path("preview.jpg"),
        rating="s",
        width=180,
        height=180,
        fetched_at="2026-05-14T16:00:00+00:00",
        last_used_at="2026-05-14T16:00:00+00:00",
        byte_size=0,
    )

    stored = store.save_cached_image_asset(asset, b"image-bytes")
    loaded = store.load_cached_image_asset("preview:12345")

    assert loaded == stored
    assert stored.local_path.exists() is True
    assert stored.local_path.read_bytes() == b"image-bytes"
    assert stored.byte_size == len(b"image-bytes")


def test_danbooru_cache_store_clear_operations_remove_cached_rows_and_files(
    tmp_path: Path,
) -> None:
    """Clear operations should drop cached metadata rows and image assets."""

    store = SqliteDanbooruCacheStore(tmp_path)
    store.save_cached_wiki_page(
        DanbooruCachedWikiPage(
            title="long_hair",
            lookup_status=DanbooruLookupStatus.FOUND,
            wiki_page=_wiki_page_record(),
            fetched_at="2026-05-14T16:00:00+00:00",
            expires_at="2026-05-21T16:00:00+00:00",
        )
    )
    store.save_cached_image_asset(
        DanbooruCachedImageAsset(
            cache_key="preview:12345",
            source_url="https://cdn.donmai.us/180x180/example.jpg",
            local_path=Path("preview.jpg"),
            rating="s",
            width=180,
            height=180,
            fetched_at="2026-05-14T16:00:00+00:00",
            last_used_at="2026-05-14T16:00:00+00:00",
            byte_size=0,
        ),
        b"image-bytes",
    )

    summary = store.cache_summary()
    assert summary.metadata_entry_count == 1
    assert summary.image_entry_count == 1

    store.save_cached_post_search(
        DanbooruCachedPostSearch(
            tag_name="long_hair",
            post_ids=(12345,),
            fetched_at="2026-05-14T16:00:00+00:00",
            expires_at="2026-05-14T22:00:00+00:00",
        )
    )
    assert store.cache_summary().metadata_entry_count == 2

    store.clear_text_cache()
    assert store.load_cached_wiki_page("long_hair") is None
    assert store.load_cached_post_search("long_hair") is None
    assert store.cache_summary().image_entry_count == 1

    store.clear_image_cache()
    assert store.load_cached_image_asset("preview:12345") is None
    assert store.cache_summary().image_entry_count == 0


def _wiki_page_record(*, title: str = "long_hair") -> DanbooruWikiPageRecord:
    """Return one representative wiki page record for cache tests."""

    return DanbooruWikiPageRecord(
        wiki_page_id=10,
        created_at="2008-03-29T11:38:25.828-04:00",
        updated_at="2026-04-19T14:10:46.625-04:00",
        title=title,
        body="h4. Definition\n\nHair that extends below the shoulders.",
        other_names=("long locks",),
        category_name="general",
    )


def _tag_record() -> DanbooruTagRecord:
    """Return one representative tag record for cache tests."""

    return DanbooruTagRecord(
        tag_id=11,
        created_at="2013-02-28T00:04:36.440-05:00",
        updated_at="2019-08-26T20:40:54.525-04:00",
        name="long_hair",
        category=0,
        post_count=5786558,
        is_deprecated=False,
    )


def _post_record() -> DanbooruPostRecord:
    """Return one representative post record for cache tests."""

    return DanbooruPostRecord(
        post_id=12345,
        created_at="2026-05-01T10:00:00.000-04:00",
        updated_at="2026-05-13T12:30:00.000-04:00",
        source="https://artist.example/post/12345",
        md5="0123456789abcdef0123456789abcdef",
        rating="s",
        tag_string="1girl long_hair smile",
        tag_string_general="1girl long_hair smile",
        tag_string_artist="artist_name",
        tag_string_copyright="series_name",
        tag_string_character="heroine",
        tag_string_meta="commentary",
        file_url="https://cdn.donmai.us/original/example.jpg",
        large_file_url="https://cdn.donmai.us/sample/example.jpg",
        preview_file_url="https://cdn.donmai.us/180x180/example.jpg",
    )

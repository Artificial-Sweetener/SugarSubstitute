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

"""Persist cached Danbooru text and post metadata in SQLite."""

from __future__ import annotations

from contextlib import closing
import json
import sqlite3
from pathlib import Path

from substitute.application.cache_lifecycle.cache_ids import (
    CACHE_ID_DANBOORU_METADATA,
)
from substitute.domain.danbooru import (
    DanbooruCachedPost,
    DanbooruCachedPostSearch,
    DanbooruCachedTag,
    DanbooruCachedWikiPage,
    DanbooruLookupStatus,
    DanbooruPostRecord,
    DanbooruTagRecord,
    DanbooruWikiPageRecord,
)
from substitute.infrastructure.cache_lifecycle.sqlite_recovery import (
    initialize_recoverable_sqlite,
)

_DATABASE_FILE_NAME = "danbooru_cache.sqlite3"


class SqliteDanbooruMetadataStore:
    """Store Danbooru wiki, tag, post, and search cache records in SQLite."""

    def __init__(self, cache_dir: Path) -> None:
        """Store the metadata database path and initialize its schema."""

        self._cache_dir = cache_dir
        self._database_path = cache_dir / _DATABASE_FILE_NAME
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        initialize_recoverable_sqlite(
            self._database_path,
            cache_id=CACHE_ID_DANBOORU_METADATA,
            initialize=self._create_schema,
            select_database=self._select_database,
        )

    def _select_database(self, database_path: Path) -> None:
        """Select a recovery database when the invalid file remains locked."""

        self._database_path = database_path

    def load_cached_wiki_page(self, title: str) -> DanbooruCachedWikiPage | None:
        """Return one cached wiki page entry by title when present."""

        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                select title, lookup_status, wiki_page_id, remote_created_at,
                       remote_updated_at, body, other_names_json, category_name,
                       fetched_at, expires_at, error
                  from danbooru_wiki_pages
                 where title = ?
                """,
                (title,),
            ).fetchone()
        if row is None:
            return None
        return _cached_wiki_page_from_row(row)

    def save_cached_wiki_page(self, entry: DanbooruCachedWikiPage) -> None:
        """Persist one cached wiki page entry."""

        page = entry.wiki_page
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                insert into danbooru_wiki_pages(
                    title, lookup_status, wiki_page_id, remote_created_at,
                    remote_updated_at, body, other_names_json, category_name,
                    fetched_at, expires_at, error
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(title) do update set
                    lookup_status=excluded.lookup_status,
                    wiki_page_id=excluded.wiki_page_id,
                    remote_created_at=excluded.remote_created_at,
                    remote_updated_at=excluded.remote_updated_at,
                    body=excluded.body,
                    other_names_json=excluded.other_names_json,
                    category_name=excluded.category_name,
                    fetched_at=excluded.fetched_at,
                    expires_at=excluded.expires_at,
                    error=excluded.error
                """,
                (
                    entry.title,
                    entry.lookup_status.value,
                    None if page is None else page.wiki_page_id,
                    None if page is None else page.created_at,
                    None if page is None else page.updated_at,
                    None if page is None else page.body,
                    None
                    if page is None
                    else json.dumps(page.other_names, ensure_ascii=True),
                    None if page is None else page.category_name,
                    entry.fetched_at,
                    entry.expires_at,
                    entry.error,
                ),
            )

    def list_cached_wiki_pages(self) -> tuple[DanbooruCachedWikiPage, ...]:
        """Return all cached wiki page entries in deterministic title order."""

        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                select title, lookup_status, wiki_page_id, remote_created_at,
                       remote_updated_at, body, other_names_json, category_name,
                       fetched_at, expires_at, error
                  from danbooru_wiki_pages
              order by title asc
                """
            ).fetchall()
        return tuple(_cached_wiki_page_from_row(row) for row in rows)

    def load_cached_tag(self, name: str) -> DanbooruCachedTag | None:
        """Return one cached tag entry by exact name when present."""

        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                select name, lookup_status, tag_id, remote_created_at,
                       remote_updated_at, category, post_count, is_deprecated,
                       fetched_at, expires_at, error
                  from danbooru_tags
                 where name = ?
                """,
                (name,),
            ).fetchone()
        if row is None:
            return None
        return _cached_tag_from_row(row)

    def save_cached_tag(self, entry: DanbooruCachedTag) -> None:
        """Persist one cached tag entry."""

        tag = entry.tag
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                insert into danbooru_tags(
                    name, lookup_status, tag_id, remote_created_at,
                    remote_updated_at, category, post_count, is_deprecated,
                    fetched_at, expires_at, error
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(name) do update set
                    lookup_status=excluded.lookup_status,
                    tag_id=excluded.tag_id,
                    remote_created_at=excluded.remote_created_at,
                    remote_updated_at=excluded.remote_updated_at,
                    category=excluded.category,
                    post_count=excluded.post_count,
                    is_deprecated=excluded.is_deprecated,
                    fetched_at=excluded.fetched_at,
                    expires_at=excluded.expires_at,
                    error=excluded.error
                """,
                (
                    entry.name,
                    entry.lookup_status.value,
                    None if tag is None else tag.tag_id,
                    None if tag is None else tag.created_at,
                    None if tag is None else tag.updated_at,
                    None if tag is None else tag.category,
                    None if tag is None else tag.post_count,
                    None if tag is None else int(tag.is_deprecated),
                    entry.fetched_at,
                    entry.expires_at,
                    entry.error,
                ),
            )

    def load_cached_post(self, post_id: int) -> DanbooruCachedPost | None:
        """Return one cached post entry by post identifier when present."""

        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                select post_id, lookup_status, remote_created_at, remote_updated_at,
                       source, md5, rating, tag_string, tag_string_general,
                       tag_string_artist, tag_string_copyright,
                       tag_string_character, tag_string_meta, file_url,
                       large_file_url, preview_file_url, fetched_at, expires_at, error
                  from danbooru_posts
                 where post_id = ?
                """,
                (post_id,),
            ).fetchone()
        if row is None:
            return None
        return _cached_post_from_row(row)

    def save_cached_post(self, entry: DanbooruCachedPost) -> None:
        """Persist one cached post entry."""

        post = entry.post
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                insert into danbooru_posts(
                    post_id, lookup_status, remote_created_at, remote_updated_at,
                    source, md5, rating, tag_string, tag_string_general,
                    tag_string_artist, tag_string_copyright,
                    tag_string_character, tag_string_meta, file_url,
                    large_file_url, preview_file_url, fetched_at, expires_at, error
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(post_id) do update set
                    lookup_status=excluded.lookup_status,
                    remote_created_at=excluded.remote_created_at,
                    remote_updated_at=excluded.remote_updated_at,
                    source=excluded.source,
                    md5=excluded.md5,
                    rating=excluded.rating,
                    tag_string=excluded.tag_string,
                    tag_string_general=excluded.tag_string_general,
                    tag_string_artist=excluded.tag_string_artist,
                    tag_string_copyright=excluded.tag_string_copyright,
                    tag_string_character=excluded.tag_string_character,
                    tag_string_meta=excluded.tag_string_meta,
                    file_url=excluded.file_url,
                    large_file_url=excluded.large_file_url,
                    preview_file_url=excluded.preview_file_url,
                    fetched_at=excluded.fetched_at,
                    expires_at=excluded.expires_at,
                    error=excluded.error
                """,
                (
                    entry.post_id,
                    entry.lookup_status.value,
                    None if post is None else post.created_at,
                    None if post is None else post.updated_at,
                    None if post is None else post.source,
                    None if post is None else post.md5,
                    None if post is None else post.rating,
                    None if post is None else post.tag_string,
                    None if post is None else post.tag_string_general,
                    None if post is None else post.tag_string_artist,
                    None if post is None else post.tag_string_copyright,
                    None if post is None else post.tag_string_character,
                    None if post is None else post.tag_string_meta,
                    None if post is None else post.file_url,
                    None if post is None else post.large_file_url,
                    None if post is None else post.preview_file_url,
                    entry.fetched_at,
                    entry.expires_at,
                    entry.error,
                ),
            )

    def load_cached_post_search(self, tag_name: str) -> DanbooruCachedPostSearch | None:
        """Return one cached tag-post search entry when present."""

        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                select tag_name, post_ids_json, fetched_at, expires_at
                  from danbooru_post_searches
                 where tag_name = ?
                """,
                (tag_name,),
            ).fetchone()
        if row is None:
            return None
        return _cached_post_search_from_row(row)

    def save_cached_post_search(self, entry: DanbooruCachedPostSearch) -> None:
        """Persist one cached tag-post search entry."""

        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                insert into danbooru_post_searches(
                    tag_name, post_ids_json, fetched_at, expires_at
                ) values (?, ?, ?, ?)
                on conflict(tag_name) do update set
                    post_ids_json=excluded.post_ids_json,
                    fetched_at=excluded.fetched_at,
                    expires_at=excluded.expires_at
                """,
                (
                    entry.tag_name,
                    json.dumps(entry.post_ids, ensure_ascii=True),
                    entry.fetched_at,
                    entry.expires_at,
                ),
            )

    def clear_text_cache(self) -> None:
        """Delete cached wiki, tag, and post metadata."""

        with closing(self._connect()) as connection, connection:
            connection.execute("delete from danbooru_wiki_pages")
            connection.execute("delete from danbooru_tags")
            connection.execute("delete from danbooru_posts")
            connection.execute("delete from danbooru_post_searches")

    def entry_count(self) -> int:
        """Return the current cached metadata entry count."""

        with closing(self._connect()) as connection:
            wiki_count = _count_rows(connection, "danbooru_wiki_pages")
            tag_count = _count_rows(connection, "danbooru_tags")
            post_count = _count_rows(connection, "danbooru_posts")
            post_search_count = _count_rows(connection, "danbooru_post_searches")
        return wiki_count + tag_count + post_count + post_search_count

    def _connect(self) -> sqlite3.Connection:
        """Return one SQLite connection configured for row access."""

        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _create_schema(self) -> None:
        """Create Danbooru cache tables when absent."""

        with closing(self._connect()) as connection, connection:
            connection.executescript(_SCHEMA_SQL)


def _cached_wiki_page_from_row(row: sqlite3.Row) -> DanbooruCachedWikiPage:
    """Return one cached wiki-page entry from a SQLite row."""

    lookup_status = DanbooruLookupStatus(str(row["lookup_status"]))
    wiki_page = None
    if row["wiki_page_id"] is not None:
        wiki_page = DanbooruWikiPageRecord(
            wiki_page_id=int(row["wiki_page_id"]),
            created_at=_optional_str(row["remote_created_at"]),
            updated_at=_optional_str(row["remote_updated_at"]),
            title=str(row["title"]),
            body=str(row["body"]),
            other_names=_str_tuple_from_json(_optional_str(row["other_names_json"])),
            category_name=_optional_str(row["category_name"]),
        )
    return DanbooruCachedWikiPage(
        title=str(row["title"]),
        lookup_status=lookup_status,
        wiki_page=wiki_page,
        fetched_at=str(row["fetched_at"]),
        expires_at=str(row["expires_at"]),
        error=str(row["error"]),
    )


def _cached_tag_from_row(row: sqlite3.Row) -> DanbooruCachedTag:
    """Return one cached tag entry from a SQLite row."""

    lookup_status = DanbooruLookupStatus(str(row["lookup_status"]))
    tag = None
    if row["tag_id"] is not None:
        tag = DanbooruTagRecord(
            tag_id=int(row["tag_id"]),
            created_at=_optional_str(row["remote_created_at"]),
            updated_at=_optional_str(row["remote_updated_at"]),
            name=str(row["name"]),
            category=int(row["category"]),
            post_count=int(row["post_count"]),
            is_deprecated=bool(row["is_deprecated"]),
        )
    return DanbooruCachedTag(
        name=str(row["name"]),
        lookup_status=lookup_status,
        tag=tag,
        fetched_at=str(row["fetched_at"]),
        expires_at=str(row["expires_at"]),
        error=str(row["error"]),
    )


def _cached_post_from_row(row: sqlite3.Row) -> DanbooruCachedPost:
    """Return one cached post entry from a SQLite row."""

    lookup_status = DanbooruLookupStatus(str(row["lookup_status"]))
    post = None
    if row["source"] is not None:
        post = DanbooruPostRecord(
            post_id=int(row["post_id"]),
            created_at=_optional_str(row["remote_created_at"]),
            updated_at=_optional_str(row["remote_updated_at"]),
            source=str(row["source"]),
            md5=_optional_str(row["md5"]),
            rating=_optional_str(row["rating"]),
            tag_string=str(row["tag_string"]),
            tag_string_general=str(row["tag_string_general"]),
            tag_string_artist=str(row["tag_string_artist"]),
            tag_string_copyright=str(row["tag_string_copyright"]),
            tag_string_character=str(row["tag_string_character"]),
            tag_string_meta=str(row["tag_string_meta"]),
            file_url=_optional_str(row["file_url"]),
            large_file_url=_optional_str(row["large_file_url"]),
            preview_file_url=_optional_str(row["preview_file_url"]),
        )
    return DanbooruCachedPost(
        post_id=int(row["post_id"]),
        lookup_status=lookup_status,
        post=post,
        fetched_at=str(row["fetched_at"]),
        expires_at=str(row["expires_at"]),
        error=str(row["error"]),
    )


def _cached_post_search_from_row(row: sqlite3.Row) -> DanbooruCachedPostSearch:
    """Return one cached tag-post search entry from a SQLite row."""

    return DanbooruCachedPostSearch(
        tag_name=str(row["tag_name"]),
        post_ids=_int_tuple_from_json(str(row["post_ids_json"])),
        fetched_at=str(row["fetched_at"]),
        expires_at=str(row["expires_at"]),
    )


def _str_tuple_from_json(raw_value: str | None) -> tuple[str, ...]:
    """Return a tuple of strings from one JSON-encoded list field."""

    if raw_value is None:
        return ()
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError:
        return ()
    if not isinstance(payload, list):
        return ()
    return tuple(item for item in payload if isinstance(item, str))


def _int_tuple_from_json(raw_value: str) -> tuple[int, ...]:
    """Return a tuple of integers from one JSON-encoded list field."""

    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError:
        return ()
    if not isinstance(payload, list):
        return ()
    return tuple(item for item in payload if isinstance(item, int))


def _count_rows(connection: sqlite3.Connection, table_name: str) -> int:
    """Return the row count for one cache table."""

    return int(connection.execute(f"select count(*) from {table_name}").fetchone()[0])


def _optional_str(value: object) -> str | None:
    """Return one optional SQLite text value as a Python string."""

    return value if isinstance(value, str) else None


_SCHEMA_SQL = """
create table if not exists danbooru_wiki_pages (
  title text primary key,
  lookup_status text not null,
  wiki_page_id integer,
  remote_created_at text,
  remote_updated_at text,
  body text,
  other_names_json text,
  category_name text,
  fetched_at text not null,
  expires_at text not null,
  error text not null default ''
);

create table if not exists danbooru_tags (
  name text primary key,
  lookup_status text not null,
  tag_id integer,
  remote_created_at text,
  remote_updated_at text,
  category integer,
  post_count integer,
  is_deprecated integer,
  fetched_at text not null,
  expires_at text not null,
  error text not null default ''
);

create table if not exists danbooru_posts (
  post_id integer primary key,
  lookup_status text not null,
  remote_created_at text,
  remote_updated_at text,
  source text,
  md5 text,
  rating text,
  tag_string text,
  tag_string_general text,
  tag_string_artist text,
  tag_string_copyright text,
  tag_string_character text,
  tag_string_meta text,
  file_url text,
  large_file_url text,
  preview_file_url text,
  fetched_at text not null,
  expires_at text not null,
  error text not null default ''
);

create table if not exists danbooru_post_searches (
  tag_name text primary key,
  post_ids_json text not null,
  fetched_at text not null,
  expires_at text not null
);

"""


__all__ = ["SqliteDanbooruMetadataStore"]

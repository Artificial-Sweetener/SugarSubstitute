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

"""Persist Danbooru preview image records and content-addressed files."""

from __future__ import annotations

from contextlib import closing
import hashlib
import os
from pathlib import Path
import sqlite3

from substitute.application.cache_lifecycle.cache_ids import CACHE_ID_DANBOORU_IMAGES
from substitute.domain.danbooru import DanbooruCachedImageAsset
from substitute.infrastructure.cache_lifecycle.sqlite_recovery import (
    initialize_recoverable_sqlite,
)

_DATABASE_FILE_NAME = "danbooru_images.sqlite3"
_IMAGE_DIRECTORY_NAME = "assets"


class SqliteDanbooruImageCacheStore:
    """Own Danbooru preview metadata and binary asset lifecycle."""

    def __init__(self, cache_dir: Path) -> None:
        """Initialize image metadata and binary cache namespaces."""

        self._database_path = cache_dir / _DATABASE_FILE_NAME
        self._image_cache_dir = cache_dir / _IMAGE_DIRECTORY_NAME
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._image_cache_dir.mkdir(parents=True, exist_ok=True)
        initialize_recoverable_sqlite(
            self._database_path,
            cache_id=CACHE_ID_DANBOORU_IMAGES,
            initialize=self._create_schema,
            select_database=self._select_database,
        )

    def _select_database(self, database_path: Path) -> None:
        """Select a recovery database when the invalid file remains locked."""

        self._database_path = database_path

    def load_cached_image_asset(
        self,
        cache_key: str,
    ) -> DanbooruCachedImageAsset | None:
        """Return one cached preview image asset when its file remains present."""

        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                select cache_key, source_url, local_path, rating, width, height,
                       fetched_at, last_used_at, byte_size
                  from danbooru_image_assets
                 where cache_key = ?
                """,
                (cache_key,),
            ).fetchone()
        if row is None:
            return None
        asset = _cached_image_asset_from_row(row)
        if (
            asset.local_path.is_file()
            and asset.local_path.stat().st_size == asset.byte_size
        ):
            return asset
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "delete from danbooru_image_assets where cache_key = ?",
                (cache_key,),
            )
        return None

    def save_cached_image_asset(
        self,
        asset: DanbooruCachedImageAsset,
        image_bytes: bytes,
    ) -> DanbooruCachedImageAsset:
        """Atomically persist one preview image and commit its metadata record."""

        file_name = _image_file_name(
            asset.cache_key, asset.source_url, asset.local_path
        )
        local_path = self._image_cache_dir / file_name
        temp_path = local_path.with_name(f"{local_path.name}.tmp")
        try:
            with temp_path.open("wb") as stream:
                stream.write(image_bytes)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, local_path)
        finally:
            temp_path.unlink(missing_ok=True)
        stored_asset = DanbooruCachedImageAsset(
            cache_key=asset.cache_key,
            source_url=asset.source_url,
            local_path=local_path,
            rating=asset.rating,
            width=asset.width,
            height=asset.height,
            fetched_at=asset.fetched_at,
            last_used_at=asset.last_used_at,
            byte_size=len(image_bytes),
        )
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                insert into danbooru_image_assets(
                    cache_key, source_url, local_path, rating, width, height,
                    fetched_at, last_used_at, byte_size
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(cache_key) do update set
                    source_url=excluded.source_url,
                    local_path=excluded.local_path,
                    rating=excluded.rating,
                    width=excluded.width,
                    height=excluded.height,
                    fetched_at=excluded.fetched_at,
                    last_used_at=excluded.last_used_at,
                    byte_size=excluded.byte_size
                """,
                (
                    stored_asset.cache_key,
                    stored_asset.source_url,
                    str(stored_asset.local_path),
                    stored_asset.rating,
                    stored_asset.width,
                    stored_asset.height,
                    stored_asset.fetched_at,
                    stored_asset.last_used_at,
                    stored_asset.byte_size,
                ),
            )
        return stored_asset

    def touch_cached_image_asset(self, cache_key: str, *, last_used_at: str) -> None:
        """Update one cached image asset's last-used timestamp when present."""

        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                update danbooru_image_assets
                   set last_used_at = ?
                 where cache_key = ?
                """,
                (last_used_at, cache_key),
            )

    def clear(self) -> None:
        """Delete cached preview image files and their metadata rows."""

        for path in self._image_cache_dir.iterdir():
            if path.is_file():
                path.unlink()
        with closing(self._connect()) as connection, connection:
            connection.execute("delete from danbooru_image_assets")

    def summary(self) -> tuple[int, int]:
        """Return cached image row count and recorded binary byte usage."""

        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                select count(*) as image_count,
                       coalesce(sum(byte_size), 0) as image_bytes
                  from danbooru_image_assets
                """
            ).fetchone()
        return int(row["image_count"]), int(row["image_bytes"])

    def _connect(self) -> sqlite3.Connection:
        """Return one SQLite connection configured for row access."""

        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _create_schema(self) -> None:
        """Create the cohesive image cache schema when absent."""

        with closing(self._connect()) as connection, connection:
            connection.executescript(_SCHEMA_SQL)


def _cached_image_asset_from_row(row: sqlite3.Row) -> DanbooruCachedImageAsset:
    """Return one cached image asset from a SQLite row."""

    return DanbooruCachedImageAsset(
        cache_key=str(row["cache_key"]),
        source_url=str(row["source_url"]),
        local_path=Path(str(row["local_path"])),
        rating=_optional_str(row["rating"]),
        width=_optional_int(row["width"]),
        height=_optional_int(row["height"]),
        fetched_at=str(row["fetched_at"]),
        last_used_at=str(row["last_used_at"]),
        byte_size=int(row["byte_size"]),
    )


def _image_file_name(cache_key: str, source_url: str, local_path: Path) -> str:
    """Return one stable cache-file name for a preview image asset."""

    suffix = local_path.suffix or Path(source_url).suffix or ".img"
    digest = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()
    return f"{digest}{suffix}"


def _optional_str(value: object) -> str | None:
    """Return one optional SQLite text value as a Python string."""

    return value if isinstance(value, str) else None


def _optional_int(value: object) -> int | None:
    """Return one optional SQLite integer value as a Python int."""

    return value if isinstance(value, int) else None


_SCHEMA_SQL = """
create table if not exists danbooru_image_assets (
  cache_key text primary key,
  source_url text not null,
  local_path text not null,
  rating text,
  width integer,
  height integer,
  fetched_at text not null,
  last_used_at text not null,
  byte_size integer not null default 0
);
"""


__all__ = ["SqliteDanbooruImageCacheStore"]

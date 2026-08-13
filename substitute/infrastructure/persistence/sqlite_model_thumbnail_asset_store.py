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

"""Persist model thumbnail source records and Qt-ready variants in SQLite."""

from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
from typing import Iterator

from substitute.application.cache_lifecycle.cache_ids import CACHE_ID_MODEL_THUMBNAILS
from substitute.domain.model_metadata import (
    ThumbnailAsset,
    ThumbnailStoreResult,
    ThumbnailVariant,
)
from substitute.infrastructure.cache_lifecycle.sqlite_recovery import (
    initialize_recoverable_sqlite,
)

_DATABASE_NAME = "model_thumbnails.sqlite3"
_SCHEMA_VERSION = "1"


class SqliteModelThumbnailAssetStore:
    """Own prepared model thumbnail source metadata and binary variants."""

    def __init__(self, thumbnail_root: Path) -> None:
        """Open the isolated thumbnail cache database and initialize its schema."""

        self._root = thumbnail_root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        self._database_path = self._root / _DATABASE_NAME
        initialize_recoverable_sqlite(
            self._database_path,
            cache_id=CACHE_ID_MODEL_THUMBNAILS,
            initialize=self._create_or_validate_database,
            select_database=self._select_database,
        )

    def _select_database(self, database_path: Path) -> None:
        """Select a recovery database when the invalid file remains locked."""

        self._database_path = database_path

    def replace(self, sha256: str, thumbnail: ThumbnailStoreResult | None) -> None:
        """Replace every thumbnail artifact associated with one model hash."""

        normalized_sha256 = sha256.upper()
        with self._transaction() as connection:
            connection.execute(
                "delete from thumbnail_sources where sha256 = ?",
                (normalized_sha256,),
            )
            if thumbnail is None:
                return
            connection.execute(
                """
                insert into thumbnail_sources(
                  sha256, source, selection_policy, source_image_url,
                  source_image_id, nsfw, nsfw_level, source_width, source_height,
                  downloaded_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized_sha256,
                    thumbnail.source,
                    thumbnail.selection_policy,
                    thumbnail.source_image_url,
                    thumbnail.source_image_id,
                    _optional_bool_to_int(thumbnail.nsfw),
                    json.dumps(thumbnail.nsfw_level),
                    thumbnail.source_width,
                    thumbnail.source_height,
                    thumbnail.downloaded_at,
                ),
            )
            assets_by_key = {asset.storage_key: asset for asset in thumbnail.assets}
            connection.executemany(
                """
                insert into thumbnail_variants(
                  sha256, storage_key, role, size, width, height, qt_format,
                  bytes_per_line, content_format, byte_size, payload
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _thumbnail_variant_row(normalized_sha256, variant, assets_by_key)
                    for variant in thumbnail.variants
                    if variant.storage_key in assets_by_key
                ),
            )

    def result_for_sha256(self, sha256: str) -> ThumbnailStoreResult | None:
        """Return selected thumbnail metadata without loading variant payloads."""

        with self._connect() as connection:
            row = connection.execute(
                "select * from thumbnail_sources where sha256 = ?",
                (sha256.upper(),),
            ).fetchone()
            if row is None:
                return None
            variants = tuple(
                ThumbnailVariant(
                    storage_key=str(variant_row["storage_key"]),
                    role=str(variant_row["role"]),
                    size=int(variant_row["size"]),
                    width=int(variant_row["width"]),
                    height=int(variant_row["height"]),
                    content_format=str(variant_row["content_format"]),
                    byte_size=int(variant_row["byte_size"]),
                )
                for variant_row in connection.execute(
                    """
                    select storage_key, role, size, width, height,
                           content_format, byte_size
                    from thumbnail_variants
                    where sha256 = ?
                    order by role, size
                    """,
                    (sha256.upper(),),
                ).fetchall()
            )
        return ThumbnailStoreResult(
            source=str(row["source"]),
            selection_policy=str(row["selection_policy"]),
            source_image_url=str(row["source_image_url"]),
            source_image_id=_optional_int(row["source_image_id"]),
            nsfw=_optional_bool_from_int(row["nsfw"]),
            nsfw_level=_optional_json_scalar(row["nsfw_level"]),
            source_width=_optional_int(row["source_width"]),
            source_height=_optional_int(row["source_height"]),
            variants=variants,
            downloaded_at=str(row["downloaded_at"]),
        )

    def has_variants(self, sha256: str) -> bool:
        """Return whether one model hash has at least one prepared variant."""

        with self._connect() as connection:
            row = connection.execute(
                "select count(*) as count from thumbnail_variants where sha256 = ?",
                (sha256.upper(),),
            ).fetchone()
        return int(row["count"]) > 0

    def read_thumbnail_asset(self, storage_key: str) -> ThumbnailAsset | None:
        """Return one prepared thumbnail asset, or ``None`` when missing."""

        with self._connect() as connection:
            row = connection.execute(
                """
                select storage_key, width, height, qt_format, bytes_per_line,
                       content_format, payload
                from thumbnail_variants
                where storage_key = ?
                """,
                (storage_key,),
            ).fetchone()
        if row is None:
            return None
        return ThumbnailAsset(
            storage_key=str(row["storage_key"]),
            width=int(row["width"]),
            height=int(row["height"]),
            qt_format=int(row["qt_format"]),
            bytes_per_line=int(row["bytes_per_line"]),
            content_format=str(row["content_format"]),
            payload=bytes(row["payload"]),
        )

    def summary(self) -> tuple[int, int, int]:
        """Return source count, variant count, and variant byte usage."""

        with self._connect() as connection:
            source_count = int(
                connection.execute(
                    "select count(*) as count from thumbnail_sources"
                ).fetchone()["count"]
            )
            variant_row = connection.execute(
                """
                select count(*) as count, coalesce(sum(byte_size), 0) as bytes
                from thumbnail_variants
                """
            ).fetchone()
        return source_count, int(variant_row["count"]), int(variant_row["bytes"])

    def clear(self) -> None:
        """Delete all prepared model thumbnail sources and variants."""

        with self._transaction() as connection:
            connection.execute("delete from thumbnail_sources")

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        """Yield one thumbnail database transaction."""

        with self._connect() as connection:
            try:
                connection.execute("begin")
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Yield one configured thumbnail database connection."""

        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("pragma foreign_keys = on")
            connection.execute("pragma busy_timeout = 5000")
            yield connection
        finally:
            connection.close()

    def _create_or_validate_database(self) -> None:
        """Create and validate the isolated thumbnail cache schema."""

        with self._connect() as connection:
            connection.execute("pragma journal_mode = wal")
            connection.executescript(_SCHEMA_SQL)
            row = connection.execute(
                "select value from thumbnail_schema where key = 'schema_version'"
            ).fetchone()
            if row is None:
                connection.execute(
                    "insert into thumbnail_schema(key, value) values(?, ?)",
                    ("schema_version", _SCHEMA_VERSION),
                )
            elif row["value"] != _SCHEMA_VERSION:
                raise RuntimeError(
                    "Unsupported model thumbnail SQLite schema version "
                    f"{row['value']!r}; expected {_SCHEMA_VERSION!r}."
                )
            connection.commit()


def _thumbnail_variant_row(
    sha256: str,
    variant: ThumbnailVariant,
    assets_by_key: dict[str, ThumbnailAsset],
) -> tuple[object, ...]:
    """Return the database row for one prepared thumbnail variant."""

    asset = assets_by_key[variant.storage_key]
    return (
        sha256,
        variant.storage_key,
        variant.role,
        variant.size,
        asset.width,
        asset.height,
        asset.qt_format,
        asset.bytes_per_line,
        asset.content_format,
        len(asset.payload),
        asset.payload,
    )


def _optional_bool_to_int(value: bool | None) -> int | None:
    """Encode an optional boolean for SQLite."""

    return None if value is None else int(value)


def _optional_bool_from_int(value: object) -> bool | None:
    """Decode an optional SQLite boolean."""

    return None if value is None else bool(value)


def _optional_int(value: object) -> int | None:
    """Decode an optional SQLite integer."""

    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str | bytes | bytearray):
        return int(value)
    raise TypeError(f"Expected integer-compatible SQLite value, got {type(value)!r}.")


def _optional_json_scalar(value: object) -> str | int | None:
    """Decode an optional string or integer JSON scalar."""

    parsed = json.loads(value) if isinstance(value, str) else None
    if isinstance(parsed, bool):
        return None
    return parsed if isinstance(parsed, str | int) else None


_SCHEMA_SQL = """
create table if not exists thumbnail_schema (
  key text primary key,
  value text not null
);

create table if not exists thumbnail_sources (
  sha256 text primary key,
  source text not null,
  selection_policy text not null,
  source_image_url text not null,
  source_image_id integer,
  nsfw integer,
  nsfw_level text,
  source_width integer,
  source_height integer,
  downloaded_at text not null
);

create table if not exists thumbnail_variants (
  id integer primary key autoincrement,
  sha256 text not null references thumbnail_sources(sha256) on delete cascade,
  storage_key text not null unique,
  role text not null,
  size integer not null,
  width integer not null,
  height integer not null,
  qt_format integer not null,
  bytes_per_line integer not null,
  content_format text not null,
  byte_size integer not null,
  payload blob not null,
  unique(sha256, role, size)
);

create index if not exists idx_thumbnail_variants_sha256
  on thumbnail_variants(sha256);
create index if not exists idx_thumbnail_variants_sha256_size
  on thumbnail_variants(sha256, size);
"""


__all__ = ["SqliteModelThumbnailAssetStore"]

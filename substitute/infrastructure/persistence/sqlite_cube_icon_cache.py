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

"""Persist rendered Cube Library icon variants in SQLite."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
import sqlite3
from typing import Iterator

from substitute.application.ports import CubeIconCacheKey, RenderedCubeIconAsset
from substitute.shared.logging.logger import get_logger, log_info, log_debug

_LOGGER = get_logger("infrastructure.persistence.sqlite_cube_icon_cache")
_DATABASE_NAME = "cube_icon_cache.sqlite3"
_SCHEMA_VERSION = "1"


class SqliteCubeIconCache:
    """Store Qt-ready rendered Cube Library icon variants under state."""

    def __init__(
        self,
        cache_dir: Path,
        *,
        filename: str = _DATABASE_NAME,
        clock: Callable[[], str] | None = None,
    ) -> None:
        """Open the icon cache database and initialize schema."""

        self._database_path = Path(cache_dir) / filename
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._clock = clock or _utc_now
        self._initialize_database()

    def read_rendered_icon(
        self,
        key: CubeIconCacheKey,
    ) -> RenderedCubeIconAsset | None:
        """Return one rendered icon variant and refresh its access timestamp."""

        cache_key = key.stable_hash()
        with self._transaction() as connection:
            row = connection.execute(
                """
                select cache_key, width, height, qt_format, bytes_per_line,
                       content_format, payload
                from rendered_cube_icon_variants
                where cache_key = ?
                """,
                (cache_key,),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                """
                update rendered_cube_icon_variants
                set last_accessed_at = ?
                where cache_key = ?
                """,
                (self._clock(), cache_key),
            )
            return RenderedCubeIconAsset(
                cache_key=str(row["cache_key"]),
                width=int(row["width"]),
                height=int(row["height"]),
                qt_format=int(row["qt_format"]),
                bytes_per_line=int(row["bytes_per_line"]),
                content_format=str(row["content_format"]),
                payload=bytes(row["payload"]),
            )

    def write_rendered_icon(
        self,
        key: CubeIconCacheKey,
        asset: RenderedCubeIconAsset,
    ) -> None:
        """Persist one rendered icon variant, replacing older same-key content."""

        cache_key = key.stable_hash()
        if asset.cache_key != cache_key:
            raise ValueError(
                "Rendered icon asset cache key does not match request key."
            )
        now = self._clock()
        with self._transaction() as connection:
            connection.execute(
                """
                insert or replace into rendered_cube_icon_variants(
                  cache_key, target_key, catalog_revision, cube_id,
                  cube_content_hash, icon_url, media_type, color_behavior,
                  theme_name, logical_size, device_pixel_ratio, renderer_version,
                  width, height, qt_format, bytes_per_line, content_format,
                  byte_size, payload, created_at, last_accessed_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cache_key,
                    key.target_key,
                    key.catalog_revision,
                    key.cube_id,
                    key.cube_content_hash,
                    key.icon_url,
                    key.media_type,
                    key.color_behavior,
                    key.theme_name,
                    int(key.logical_size),
                    float(key.device_pixel_ratio),
                    int(key.renderer_version),
                    int(asset.width),
                    int(asset.height),
                    int(asset.qt_format),
                    int(asset.bytes_per_line),
                    asset.content_format,
                    int(asset.byte_size),
                    asset.payload,
                    now,
                    now,
                ),
            )

    def delete_for_target(self, target_key: str) -> int:
        """Delete all rendered variants for one target key."""

        with self._transaction() as connection:
            cursor = connection.execute(
                "delete from rendered_cube_icon_variants where target_key = ?",
                (target_key,),
            )
            return int(cursor.rowcount)

    def delete_except_catalog_revision(
        self,
        target_key: str,
        catalog_revision: str,
    ) -> int:
        """Delete target variants whose catalog revision no longer matches."""

        with self._transaction() as connection:
            cursor = connection.execute(
                """
                delete from rendered_cube_icon_variants
                where target_key = ?
                  and catalog_revision != ?
                """,
                (target_key, catalog_revision),
            )
            return int(cursor.rowcount)

    def clear(self) -> int:
        """Delete all rendered icon variants."""

        with self._transaction() as connection:
            cursor = connection.execute("delete from rendered_cube_icon_variants")
            return int(cursor.rowcount)

    def prune(self, *, maximum_rows: int, maximum_bytes: int) -> int:
        """Prune least recently accessed variants over row or byte budgets."""

        with self._transaction() as connection:
            deleted_count = 0
            if maximum_rows == 0 or maximum_bytes == 0:
                cursor = connection.execute("delete from rendered_cube_icon_variants")
                deleted_count = int(cursor.rowcount)
                _log_prune(deleted_count)
                return deleted_count
            if maximum_rows > 0:
                row_count = int(
                    connection.execute(
                        "select count(*) as count from rendered_cube_icon_variants"
                    ).fetchone()["count"]
                )
                deleted_count += self._delete_oldest_rows(
                    connection,
                    max(0, row_count - maximum_rows),
                )
            if maximum_bytes > 0:
                total_bytes = self._total_bytes(connection)
                if total_bytes > maximum_bytes:
                    deleted_count += self._delete_until_under_byte_budget(
                        connection,
                        total_bytes=total_bytes,
                        maximum_bytes=maximum_bytes,
                    )
            _log_prune(deleted_count)
            return deleted_count

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        """Yield a SQLite connection inside one explicit transaction."""

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
        """Yield a configured SQLite connection for one cache operation."""

        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("pragma foreign_keys = on")
            connection.execute("pragma busy_timeout = 5000")
            yield connection
        finally:
            connection.close()

    def _initialize_database(self) -> None:
        """Create cache schema and validate stored schema version."""

        with self._connect() as connection:
            connection.execute("pragma journal_mode = wal")
            connection.executescript(_SCHEMA_SQL)
            row = connection.execute(
                "select value from cube_icon_cache_schema where key = 'schema_version'"
            ).fetchone()
            if row is None:
                connection.execute(
                    """
                    insert into cube_icon_cache_schema(key, value)
                    values('schema_version', ?)
                    """,
                    (_SCHEMA_VERSION,),
                )
            elif row["value"] != _SCHEMA_VERSION:
                raise RuntimeError(
                    "Unsupported cube icon cache SQLite schema version "
                    f"{row['value']!r}; expected {_SCHEMA_VERSION!r}."
                )
            connection.commit()
        log_debug(
            _LOGGER,
            "Initialized cube icon SQLite cache",
            database_path=self._database_path,
            schema_version=_SCHEMA_VERSION,
        )

    def _delete_oldest_rows(
        self,
        connection: sqlite3.Connection,
        count: int,
    ) -> int:
        """Delete the oldest accessed rows up to ``count``."""

        if count <= 0:
            return 0
        rows = connection.execute(
            """
            select cache_key
            from rendered_cube_icon_variants
            order by last_accessed_at asc, rowid asc
            limit ?
            """,
            (count,),
        ).fetchall()
        return _delete_cache_keys(connection, [str(row["cache_key"]) for row in rows])

    def _delete_until_under_byte_budget(
        self,
        connection: sqlite3.Connection,
        *,
        total_bytes: int,
        maximum_bytes: int,
    ) -> int:
        """Delete oldest rows until the total payload size is under budget."""

        cache_keys: list[str] = []
        remaining_bytes = total_bytes
        for row in connection.execute(
            """
            select cache_key, byte_size
            from rendered_cube_icon_variants
            order by last_accessed_at asc, rowid asc
            """
        ).fetchall():
            if remaining_bytes <= maximum_bytes:
                break
            cache_keys.append(str(row["cache_key"]))
            remaining_bytes -= int(row["byte_size"])
        return _delete_cache_keys(connection, cache_keys)

    def _total_bytes(self, connection: sqlite3.Connection) -> int:
        """Return the total payload bytes currently stored."""

        row = connection.execute(
            "select coalesce(sum(byte_size), 0) as total from rendered_cube_icon_variants"
        ).fetchone()
        return int(row["total"])


def _delete_cache_keys(connection: sqlite3.Connection, cache_keys: list[str]) -> int:
    """Delete rows for the supplied cache keys and return deleted count."""

    if not cache_keys:
        return 0
    placeholders = ",".join("?" for _ in cache_keys)
    cursor = connection.execute(
        f"delete from rendered_cube_icon_variants where cache_key in ({placeholders})",
        tuple(cache_keys),
    )
    return int(cursor.rowcount)


def _log_prune(deleted_count: int) -> None:
    """Log cache prune work only when it removed rows."""

    if deleted_count <= 0:
        return
    log_info(
        _LOGGER,
        "Pruned cube icon SQLite cache",
        deleted_count=deleted_count,
    )


def _utc_now() -> str:
    """Return the current UTC timestamp for cache records."""

    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


_SCHEMA_SQL = """
create table if not exists cube_icon_cache_schema (
  key text primary key,
  value text not null
);

create table if not exists rendered_cube_icon_variants (
  cache_key text primary key,
  target_key text not null,
  catalog_revision text not null,
  cube_id text not null,
  cube_content_hash text not null,
  icon_url text not null,
  media_type text not null,
  color_behavior text not null,
  theme_name text not null,
  logical_size integer not null,
  device_pixel_ratio real not null,
  renderer_version integer not null,
  width integer not null,
  height integer not null,
  qt_format integer not null,
  bytes_per_line integer not null,
  content_format text not null,
  byte_size integer not null,
  payload blob not null,
  created_at text not null,
  last_accessed_at text not null
);

create index if not exists idx_rendered_cube_icon_target
  on rendered_cube_icon_variants(target_key);
create index if not exists idx_rendered_cube_icon_catalog
  on rendered_cube_icon_variants(target_key, catalog_revision);
create index if not exists idx_rendered_cube_icon_cube
  on rendered_cube_icon_variants(target_key, cube_id);
create index if not exists idx_rendered_cube_icon_access
  on rendered_cube_icon_variants(last_accessed_at);
"""


__all__ = ["SqliteCubeIconCache"]

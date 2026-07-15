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

"""Persist Cube Library picker classifications in SQLite."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
import sqlite3
from typing import Iterator

from substitute.application.ports import (
    CachedCubePickerClassification,
    CubeClassificationCacheKey,
)
from substitute.shared.logging.logger import get_logger, log_info, log_debug

_LOGGER = get_logger("infrastructure.persistence.sqlite_cube_classification_cache")
_DATABASE_NAME = "cube_classification_cache.sqlite3"
_SCHEMA_VERSION = "1"


class SqliteCubeClassificationCache:
    """Store Cube Library picker classifications under state."""

    def __init__(
        self,
        cache_dir: Path,
        *,
        filename: str = _DATABASE_NAME,
        clock: Callable[[], str] | None = None,
    ) -> None:
        """Open the classification cache database and initialize schema."""

        self._database_path = Path(cache_dir) / filename
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._clock = clock or _utc_now
        self._initialize_database()

    def read_classification(
        self,
        key: CubeClassificationCacheKey,
    ) -> CachedCubePickerClassification | None:
        """Return one cached classification and refresh its access timestamp."""

        cache_key = key.stable_hash()
        with self._transaction() as connection:
            row = connection.execute(
                """
                select classification_json
                from cube_picker_classifications
                where cache_key = ?
                """,
                (cache_key,),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                """
                update cube_picker_classifications
                set last_accessed_at = ?
                where cache_key = ?
                """,
                (self._clock(), cache_key),
            )
            return CachedCubePickerClassification.from_json_text(
                str(row["classification_json"])
            )

    def write_classification(
        self,
        key: CubeClassificationCacheKey,
        classification: CachedCubePickerClassification,
    ) -> None:
        """Persist one classification payload, replacing older same-key content."""

        cache_key = key.stable_hash()
        now = self._clock()
        with self._transaction() as connection:
            connection.execute(
                """
                insert or replace into cube_picker_classifications(
                  cache_key, target_key, catalog_revision, cube_id,
                  cube_content_hash, cube_version, algorithm_version,
                  classification_json, created_at, last_accessed_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cache_key,
                    key.target_key,
                    key.catalog_revision,
                    key.cube_id,
                    key.cube_content_hash,
                    key.cube_version,
                    int(key.algorithm_version),
                    classification.to_json_text(),
                    now,
                    now,
                ),
            )

    def delete_for_target(self, target_key: str) -> int:
        """Delete all classification rows for one target key."""

        with self._transaction() as connection:
            cursor = connection.execute(
                "delete from cube_picker_classifications where target_key = ?",
                (target_key,),
            )
            return int(cursor.rowcount)

    def delete_except_catalog_revision(
        self,
        target_key: str,
        catalog_revision: str,
    ) -> int:
        """Delete target classifications whose catalog revision no longer matches."""

        with self._transaction() as connection:
            cursor = connection.execute(
                """
                delete from cube_picker_classifications
                where target_key = ?
                  and catalog_revision != ?
                """,
                (target_key, catalog_revision),
            )
            return int(cursor.rowcount)

    def clear(self) -> int:
        """Delete all cached classifications."""

        with self._transaction() as connection:
            cursor = connection.execute("delete from cube_picker_classifications")
            return int(cursor.rowcount)

    def prune(self, *, maximum_rows: int) -> int:
        """Prune least recently accessed classifications over a row budget."""

        with self._transaction() as connection:
            if maximum_rows == 0:
                cursor = connection.execute("delete from cube_picker_classifications")
                deleted_count = int(cursor.rowcount)
                _log_prune(deleted_count)
                return deleted_count
            if maximum_rows < 0:
                return 0
            row_count = int(
                connection.execute(
                    "select count(*) as count from cube_picker_classifications"
                ).fetchone()["count"]
            )
            deleted_count = self._delete_oldest_rows(
                connection,
                max(0, row_count - maximum_rows),
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
                """
                select value
                from cube_classification_cache_schema
                where key = 'schema_version'
                """
            ).fetchone()
            if row is None:
                connection.execute(
                    """
                    insert into cube_classification_cache_schema(key, value)
                    values('schema_version', ?)
                    """,
                    (_SCHEMA_VERSION,),
                )
            elif row["value"] != _SCHEMA_VERSION:
                raise RuntimeError(
                    "Unsupported cube classification cache SQLite schema version "
                    f"{row['value']!r}; expected {_SCHEMA_VERSION!r}."
                )
            connection.commit()
        log_debug(
            _LOGGER,
            "Initialized cube classification SQLite cache",
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
            from cube_picker_classifications
            order by last_accessed_at asc, rowid asc
            limit ?
            """,
            (count,),
        ).fetchall()
        keys = [str(row["cache_key"]) for row in rows]
        if not keys:
            return 0
        connection.executemany(
            "delete from cube_picker_classifications where cache_key = ?",
            [(key,) for key in keys],
        )
        return len(keys)


def _utc_now() -> str:
    """Return a stable UTC timestamp for cache rows."""

    return datetime.now(UTC).isoformat(timespec="microseconds")


def _log_prune(deleted_count: int) -> None:
    """Log a classification cache prune result when rows were removed."""

    if deleted_count <= 0:
        return
    log_info(
        _LOGGER,
        "Pruned cube classification SQLite cache",
        deleted_count=deleted_count,
    )


_SCHEMA_SQL = """
create table if not exists cube_classification_cache_schema (
  key text primary key,
  value text not null
);

create table if not exists cube_picker_classifications (
  cache_key text primary key,
  target_key text not null,
  catalog_revision text not null,
  cube_id text not null,
  cube_content_hash text not null,
  cube_version text not null,
  algorithm_version integer not null,
  classification_json text not null,
  created_at text not null,
  last_accessed_at text not null
);

create index if not exists idx_cube_picker_classifications_target
  on cube_picker_classifications(target_key);
create index if not exists idx_cube_picker_classifications_catalog
  on cube_picker_classifications(target_key, catalog_revision);
create index if not exists idx_cube_picker_classifications_access
  on cube_picker_classifications(last_accessed_at);
"""


__all__ = ["SqliteCubeClassificationCache"]

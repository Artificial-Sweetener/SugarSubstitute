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

"""Persist authoritative model catalog snapshots in SQLite."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3

from substitute.application.model_metadata import (
    ModelCatalogItem,
    ModelCatalogSnapshot,
    ModelThumbnailVariant,
)

_DATABASE_NAME = "model_catalog_snapshots.sqlite3"
_SCHEMA_VERSION = 1
_MAX_SNAPSHOTS_PER_KIND = 3


class SqliteModelCatalogSnapshotStore:
    """Store last-known authoritative model catalog snapshots."""

    def __init__(self, model_metadata_root: Path) -> None:
        """Create a snapshot store under the model metadata root."""

        self._root = model_metadata_root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        self._database_path = self._root / _DATABASE_NAME
        self._initialize_database()

    def load_snapshot(self, kind: str) -> ModelCatalogSnapshot | None:
        """Return the newest durable authoritative snapshot for one kind."""

        normalized_kind = kind.strip()
        with self._connect() as connection:
            snapshot_row = connection.execute(
                """
                select *
                from catalog_snapshots
                where kind = ? and authoritative = 1
                order by produced_at_utc desc, snapshot_id desc
                limit 1
                """,
                (normalized_kind,),
            ).fetchone()
            if snapshot_row is None:
                return None
            item_rows = connection.execute(
                """
                select *
                from catalog_snapshot_items
                where snapshot_id = ?
                order by order_index
                """,
                (snapshot_row["snapshot_id"],),
            ).fetchall()
        snapshot = ModelCatalogSnapshot(
            kind=normalized_kind,
            items=tuple(_item_from_row(row) for row in item_rows),
            generation=int(snapshot_row["model_generation"]),
        )
        return snapshot

    def save_snapshot(self, snapshot: ModelCatalogSnapshot) -> None:
        """Persist one accepted authoritative snapshot atomically."""

        produced_at = datetime.now(UTC).isoformat(timespec="microseconds")
        with self._transaction() as connection:
            cursor = connection.execute(
                """
                insert into catalog_snapshots(
                    kind, schema_version, catalog_revision, model_generation,
                    produced_at_utc, source, authoritative, item_count
                )
                values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.kind,
                    _SCHEMA_VERSION,
                    snapshot.generation,
                    snapshot.generation,
                    produced_at,
                    "backend-refresh",
                    1,
                    len(snapshot.items),
                ),
            )
            snapshot_id = cursor.lastrowid
            if snapshot_id is None:
                raise RuntimeError("SQLite did not return a model snapshot id.")
            for order_index, item in enumerate(snapshot.items):
                connection.execute(
                    """
                    insert into catalog_snapshot_items(
                        snapshot_id, order_index, kind, backend_value,
                        relative_path, display_name, display_subtitle, folder,
                        basename, extension, file_size, modified_at, base_model,
                        trained_words_json, tags_json, model_page_url,
                        collision_key, collision_count, has_collision, search_text,
                        provider_name, provider_model_id,
                        provider_model_version_id, provider_model_name,
                        provider_model_version_name, sha256,
                        thumbnail_variants_json
                    )
                    values (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    _item_parameters(snapshot_id, order_index, item),
                )
            self._prune_old_snapshots(connection, snapshot.kind)

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
        """Yield a configured SQLite connection."""

        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("pragma foreign_keys = on")
            connection.execute("pragma busy_timeout = 5000")
            yield connection
        finally:
            connection.close()

    def _initialize_database(self) -> None:
        """Create the snapshot schema if it does not already exist."""

        with self._connect() as connection:
            connection.execute("pragma journal_mode = wal")
            connection.executescript(_SCHEMA_SQL)
            row = connection.execute(
                "select value from snapshot_schema where key = 'schema_version'"
            ).fetchone()
            if row is None:
                connection.execute(
                    "insert into snapshot_schema(key, value) values('schema_version', ?)",
                    (str(_SCHEMA_VERSION),),
                )
            elif row["value"] != str(_SCHEMA_VERSION):
                raise RuntimeError(
                    "Unsupported model catalog snapshot schema version "
                    f"{row['value']!r}; expected {str(_SCHEMA_VERSION)!r}."
                )
            connection.commit()

    def _prune_old_snapshots(self, connection: sqlite3.Connection, kind: str) -> None:
        """Keep only a bounded number of snapshots for one kind."""

        rows = connection.execute(
            """
            select snapshot_id
            from catalog_snapshots
            where kind = ?
            order by produced_at_utc desc, snapshot_id desc
            """,
            (kind,),
        ).fetchall()
        stale_ids = tuple(
            int(row["snapshot_id"]) for row in rows[_MAX_SNAPSHOTS_PER_KIND:]
        )
        for snapshot_id in stale_ids:
            connection.execute(
                "delete from catalog_snapshots where snapshot_id = ?",
                (snapshot_id,),
            )


def _item_parameters(
    snapshot_id: int,
    order_index: int,
    item: ModelCatalogItem,
) -> tuple[object, ...]:
    """Return SQLite parameters for one catalog item."""

    return (
        snapshot_id,
        order_index,
        item.kind,
        item.backend_value,
        item.relative_path,
        item.display_name,
        item.display_subtitle,
        item.folder,
        item.basename,
        item.extension,
        item.size_bytes,
        item.modified_at,
        item.base_model,
        json.dumps(list(item.trained_words), separators=(",", ":")),
        json.dumps(list(item.tags), separators=(",", ":")),
        item.model_page_url,
        item.collision_key,
        item.collision_count,
        1 if item.has_collision else 0,
        item.search_text,
        item.provider_name,
        item.provider_model_id,
        item.provider_model_version_id,
        item.provider_model_name,
        item.provider_model_version_name,
        item.sha256,
        _thumbnail_variants_json(item.thumbnail_variants),
    )


def _item_from_row(row: sqlite3.Row) -> ModelCatalogItem:
    """Return a model catalog item from one SQLite row."""

    return ModelCatalogItem(
        kind=str(row["kind"]),
        display_name=str(row["display_name"]),
        display_subtitle=_optional_str(row["display_subtitle"]),
        backend_value=str(row["backend_value"]),
        relative_path=str(row["relative_path"]),
        folder=str(row["folder"]),
        basename=str(row["basename"]),
        extension=str(row["extension"]),
        thumbnail_variants=_thumbnail_variants_from_json(
            str(row["thumbnail_variants_json"])
        ),
        base_model=_optional_str(row["base_model"]),
        trained_words=_string_tuple_from_json(str(row["trained_words_json"])),
        tags=_string_tuple_from_json(str(row["tags_json"])),
        model_page_url=_optional_str(row["model_page_url"]),
        collision_key=str(row["collision_key"]),
        collision_count=int(row["collision_count"]),
        has_collision=bool(int(row["has_collision"])),
        search_text=str(row["search_text"]),
        provider_name=_optional_str(row["provider_name"]),
        provider_model_id=_optional_str(row["provider_model_id"]),
        provider_model_version_id=_optional_str(row["provider_model_version_id"]),
        provider_model_name=_optional_str(row["provider_model_name"]),
        provider_model_version_name=_optional_str(row["provider_model_version_name"]),
        sha256=_optional_str(row["sha256"]),
        size_bytes=_optional_int(row["file_size"]),
        modified_at=_optional_str(row["modified_at"]),
    )


def _thumbnail_variants_json(
    variants: tuple[ModelThumbnailVariant, ...],
) -> str:
    """Serialize thumbnail variants for durable storage."""

    return json.dumps(
        [
            {
                "size": variant.size,
                "storage_key": variant.storage_key,
                "width": variant.width,
                "height": variant.height,
                "content_format": variant.content_format,
                "byte_size": variant.byte_size,
                "role": variant.role,
            }
            for variant in variants
        ],
        separators=(",", ":"),
    )


def _thumbnail_variants_from_json(
    payload: str,
) -> tuple[ModelThumbnailVariant, ...]:
    """Deserialize thumbnail variants from durable storage."""

    data = json.loads(payload)
    if not isinstance(data, list):
        return ()
    variants: list[ModelThumbnailVariant] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        variants.append(
            ModelThumbnailVariant(
                size=int(item.get("size", 0)),
                storage_key=str(item.get("storage_key", "")),
                width=int(item.get("width", 0)),
                height=int(item.get("height", 0)),
                content_format=str(item.get("content_format", "")),
                byte_size=int(item.get("byte_size", 0)),
                role=str(item.get("role", "standard")),
            )
        )
    return tuple(variants)


def _string_tuple_from_json(payload: str) -> tuple[str, ...]:
    """Deserialize a JSON string list into a tuple."""

    data = json.loads(payload)
    if not isinstance(data, list):
        return ()
    return tuple(str(item) for item in data if isinstance(item, str))


def _optional_str(value: object) -> str | None:
    """Return a string value or ``None`` from SQLite data."""

    return None if value is None else str(value)


def _optional_int(value: object) -> int | None:
    """Return an integer value or ``None`` from SQLite data."""

    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str | bytes | bytearray):
        return int(value)
    raise TypeError(f"Expected SQLite integer-compatible value, got {type(value)!r}.")


_SCHEMA_SQL = """
create table if not exists snapshot_schema (
  key text primary key,
  value text not null
);

create table if not exists catalog_snapshots (
  snapshot_id integer primary key autoincrement,
  kind text not null,
  schema_version integer not null,
  catalog_revision integer not null,
  model_generation integer not null,
  produced_at_utc text not null,
  source text not null,
  authoritative integer not null,
  item_count integer not null
);

create table if not exists catalog_snapshot_items (
  snapshot_id integer not null references catalog_snapshots(snapshot_id)
    on delete cascade,
  order_index integer not null,
  kind text not null,
  backend_value text not null,
  relative_path text not null,
  display_name text not null,
  display_subtitle text,
  folder text not null,
  basename text not null,
  extension text not null,
  file_size integer,
  modified_at text,
  base_model text,
  trained_words_json text not null,
  tags_json text not null,
  model_page_url text,
  collision_key text not null,
  collision_count integer not null,
  has_collision integer not null,
  search_text text not null,
  provider_name text,
  provider_model_id text,
  provider_model_version_id text,
  provider_model_name text,
  provider_model_version_name text,
  sha256 text,
  thumbnail_variants_json text not null,
  primary key(snapshot_id, order_index)
);

create index if not exists idx_catalog_snapshots_kind_time
  on catalog_snapshots(kind, produced_at_utc, snapshot_id);
"""


__all__ = ["SqliteModelCatalogSnapshotStore"]

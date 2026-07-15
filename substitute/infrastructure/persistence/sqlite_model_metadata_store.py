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

"""Persist model metadata and Qt-ready thumbnails in SQLite."""

from __future__ import annotations

from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
import json
import sqlite3
from typing import Iterator, cast

from substitute.domain.common import JsonObject
from substitute.application.ports.civitai_cache_repository import CivitaiCacheSummary
from substitute.domain.model_metadata import (
    CivitaiFile,
    CivitaiImage,
    CivitaiModelVersion,
    LocalModelEvidence,
    ModelMetadataCacheRecord,
    ThumbnailAsset,
    ThumbnailSelectionStatus,
    ThumbnailStoreResult,
    ThumbnailVariant,
)
from substitute.domain.model_metadata.thumbnail_policy import FirstSfwThumbnailPolicy

_SCHEMA_VERSION = "3"
_THUMBNAIL_POLICY_VERSION = 3
_DATABASE_NAME = "model_metadata.sqlite3"


class SqliteModelMetadataStore:
    """Own the SQLite-backed model metadata catalog and thumbnail asset cache."""

    def __init__(
        self,
        model_metadata_root: Path,
        *,
        thumbnail_policy_key: str | None = None,
    ) -> None:
        """Open a SQLite cache under the model metadata root and initialize schema."""

        self._root = model_metadata_root.resolve()
        self._thumbnail_policy_key = (
            thumbnail_policy_key or FirstSfwThumbnailPolicy().selection_policy
        )
        self._root.mkdir(parents=True, exist_ok=True)
        self._database_path = self._root / _DATABASE_NAME
        self._initialize_database()

    def is_fresh(self, evidence: LocalModelEvidence) -> bool:
        """Return whether cached provider metadata is fresh for local evidence."""

        with self._connect() as connection:
            row = connection.execute(
                """
                select target_id, root_id, relative_path, kind, backend_value,
                       display_name, size_bytes, modified_at, provider_status,
                       thumbnail_status, thumbnail_policy,
                       thumbnail_policy_version
                from model_metadata_records
                where sha256 = ?
                """,
                (evidence.sha256.upper(),),
            ).fetchone()
            if row is None:
                return False
            if (
                row["target_id"] != evidence.target_id
                or row["root_id"] != evidence.root_id
                or row["relative_path"] != evidence.relative_path
                or row["kind"] != evidence.kind
                or row["backend_value"] != evidence.value
                or row["display_name"] != evidence.display_name
                or row["size_bytes"] != evidence.size_bytes
                or row["modified_at"] != evidence.modified_at
            ):
                return False
            if row["provider_status"] == "stale":
                return False
            if row["provider_status"] != "found":
                return True
            if (
                row["thumbnail_policy"] != self._thumbnail_policy_key
                or row["thumbnail_policy_version"] != _THUMBNAIL_POLICY_VERSION
            ):
                return False
            if row["thumbnail_status"] != ThumbnailSelectionStatus.SELECTED.value:
                return True
            variant_count = connection.execute(
                """
                select count(*) as count
                from thumbnail_variants
                where sha256 = ?
                """,
                (evidence.sha256.upper(),),
            ).fetchone()["count"]
            return int(variant_count) > 0

    def record_for_sha256(self, sha256: str) -> ModelMetadataCacheRecord | None:
        """Return one cached metadata record by SHA256 when available."""

        with self._connect() as connection:
            row = connection.execute(
                """
                select *
                from model_metadata_records
                where sha256 = ?
                """,
                (sha256.upper(),),
            ).fetchone()
            if row is None:
                return None
            return self._record_from_row(connection, row)

    def save_record(self, record: ModelMetadataCacheRecord) -> None:
        """Persist one enriched provider record and any prepared thumbnail assets."""

        normalized_record = replace(
            record,
            local=replace(record.local, sha256=record.local.sha256.upper()),
        )
        with self._transaction() as connection:
            self._delete_record(connection, normalized_record.local.sha256)
            self._insert_record(connection, normalized_record)
            if normalized_record.provider is not None:
                self._insert_provider(connection, normalized_record)
            if normalized_record.thumbnail is not None:
                self._insert_thumbnail(connection, normalized_record)

    def save_not_found(self, evidence: LocalModelEvidence, *, fetched_at: str) -> None:
        """Persist a provider-not-found result for one local model."""

        normalized_evidence = replace(evidence, sha256=evidence.sha256.upper())
        record = ModelMetadataCacheRecord(
            schema_version=1,
            local=normalized_evidence,
            provider=None,
            provider_status="not-found",
            thumbnail=None,
            thumbnail_status=ThumbnailSelectionStatus.NO_SFW_IMAGE,
            updated_at=fetched_at,
        )
        self.save_record(record)

    def save_local_evidence(
        self,
        evidence: LocalModelEvidence,
        *,
        updated_at: str,
    ) -> None:
        """Persist local model hash evidence without claiming provider freshness."""

        normalized_evidence = replace(evidence, sha256=evidence.sha256.upper())
        record = ModelMetadataCacheRecord(
            schema_version=1,
            local=normalized_evidence,
            provider=None,
            provider_status="stale",
            thumbnail=None,
            thumbnail_status=ThumbnailSelectionStatus.NO_SFW_IMAGE,
            updated_at=updated_at,
        )
        self.save_record(record)

    def list_records(
        self,
        *,
        kind: str | None = None,
    ) -> tuple[ModelMetadataCacheRecord, ...]:
        """Return cached metadata records, optionally filtered by model kind."""

        where_clause = "" if kind is None else "where kind = ?"
        parameters: tuple[object, ...] = () if kind is None else (kind,)
        with self._connect() as connection:
            record_rows = connection.execute(
                f"""
                select *
                from model_metadata_records
                {where_clause}
                order by display_name collate nocase, relative_path collate nocase
                """,
                parameters,
            ).fetchall()
            return tuple(self._record_from_row(connection, row) for row in record_rows)

    def recipe_hash_revision(self, *, kind: str | None = None) -> tuple[int, str, int]:
        """Return a cheap revision token for recipe hash index invalidation."""

        where_clause = "" if kind is None else "where kind = ?"
        parameters: tuple[object, ...] = () if kind is None else (kind,)
        with self._connect() as connection:
            row = connection.execute(
                f"""
                select count(*) as record_count,
                       coalesce(max(updated_at), '') as latest_updated_at,
                       coalesce(max(rowid), 0) as latest_rowid
                from model_metadata_records
                {where_clause}
                """,
                parameters,
            ).fetchone()
            return (
                int(row["record_count"]),
                str(row["latest_updated_at"]),
                int(row["latest_rowid"]),
            )

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
            payload = bytes(row["payload"])
            return ThumbnailAsset(
                storage_key=str(row["storage_key"]),
                width=int(row["width"]),
                height=int(row["height"]),
                qt_format=int(row["qt_format"]),
                bytes_per_line=int(row["bytes_per_line"]),
                content_format=str(row["content_format"]),
                payload=payload,
            )

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
        """Yield a configured SQLite connection for one repository operation."""

        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("pragma foreign_keys = on")
            connection.execute("pragma busy_timeout = 5000")
            yield connection
        finally:
            connection.close()

    def _initialize_database(self) -> None:
        """Create schema and validate the stored schema version."""

        with self._connect() as connection:
            connection.execute("pragma journal_mode = wal")
            connection.executescript(_SCHEMA_SQL)
            row = connection.execute(
                "select value from metadata_schema where key = 'schema_version'"
            ).fetchone()
            if row is None:
                connection.execute(
                    "insert into metadata_schema(key, value) values('schema_version', ?)",
                    (_SCHEMA_VERSION,),
                )
            elif row["value"] != _SCHEMA_VERSION:
                raise RuntimeError(
                    "Unsupported model metadata SQLite schema version "
                    f"{row['value']!r}; expected {_SCHEMA_VERSION!r}."
                )
            connection.commit()

    def _delete_record(self, connection: sqlite3.Connection, sha256: str) -> None:
        """Delete any existing cache record for one SHA256 key."""

        connection.execute(
            "delete from model_metadata_records where sha256 = ?",
            (sha256,),
        )

    def _insert_record(
        self,
        connection: sqlite3.Connection,
        record: ModelMetadataCacheRecord,
    ) -> None:
        """Insert the local evidence and high-level provider statuses."""

        thumbnail_status = record.thumbnail_status.value
        connection.execute(
            """
            insert into model_metadata_records(
              sha256, target_id, root_id, relative_path, kind, backend_value,
              display_name, size_bytes, modified_at, provider, provider_status,
              thumbnail_status, thumbnail_policy, thumbnail_policy_version,
              schema_version, updated_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.local.sha256,
                record.local.target_id,
                record.local.root_id,
                record.local.relative_path,
                record.local.kind,
                record.local.value,
                record.local.display_name,
                record.local.size_bytes,
                record.local.modified_at,
                "civitai",
                record.provider_status,
                thumbnail_status,
                self._thumbnail_policy_key,
                _THUMBNAIL_POLICY_VERSION,
                record.schema_version,
                record.updated_at,
            ),
        )

    def cache_summary(self) -> CivitaiCacheSummary:
        """Return a summary of cached CivitAI metadata and thumbnails."""

        with self._connect() as connection:
            provider_record_count = int(
                connection.execute(
                    "select count(*) as count from civitai_model_versions"
                ).fetchone()["count"]
            )
            thumbnail_source_count = int(
                connection.execute(
                    "select count(*) as count from thumbnail_sources"
                ).fetchone()["count"]
            )
            thumbnail_variant_row = connection.execute(
                """
                select count(*) as count, coalesce(sum(byte_size), 0) as bytes
                from thumbnail_variants
                """
            ).fetchone()
            return CivitaiCacheSummary(
                provider_record_count=provider_record_count,
                thumbnail_source_count=thumbnail_source_count,
                thumbnail_variant_count=int(thumbnail_variant_row["count"]),
                thumbnail_bytes=int(thumbnail_variant_row["bytes"]),
            )

    def clear_civitai_thumbnails(self) -> None:
        """Delete CivitAI thumbnail sources and prepared variants."""

        with self._transaction() as connection:
            connection.execute("delete from thumbnail_variants")
            connection.execute("delete from thumbnail_sources")
            connection.execute(
                """
                update model_metadata_records
                set thumbnail_status = ?,
                    thumbnail_policy = ?,
                    thumbnail_policy_version = ?
                where provider = 'civitai'
                """,
                (
                    ThumbnailSelectionStatus.NO_SFW_IMAGE.value,
                    self._thumbnail_policy_key,
                    _THUMBNAIL_POLICY_VERSION,
                ),
            )

    def clear_civitai_metadata(self) -> None:
        """Delete provider metadata and thumbnails while preserving local evidence."""

        with self._transaction() as connection:
            connection.execute("delete from thumbnail_variants")
            connection.execute("delete from thumbnail_sources")
            connection.execute("delete from civitai_files")
            connection.execute("delete from civitai_images")
            connection.execute("delete from civitai_model_versions")
            connection.execute(
                """
                update model_metadata_records
                set provider_status = ?,
                    thumbnail_status = ?,
                    thumbnail_policy = ?,
                    thumbnail_policy_version = ?
                where provider = 'civitai'
                """,
                (
                    "stale",
                    ThumbnailSelectionStatus.NO_SFW_IMAGE.value,
                    self._thumbnail_policy_key,
                    _THUMBNAIL_POLICY_VERSION,
                ),
            )

    def _insert_provider(
        self,
        connection: sqlite3.Connection,
        record: ModelMetadataCacheRecord,
    ) -> None:
        """Insert normalized CivitAI metadata for one cache record."""

        assert record.provider is not None
        provider = record.provider
        connection.execute(
            """
            insert into civitai_model_versions(
              sha256, model_id, model_version_id, model_name, model_type,
              version_name, base_model, trained_words_json, tags_json,
              description, version_description, creator_username, creator_image,
              nsfw, nsfw_level, availability, stats_json, model_page_url,
              source_url, fetched_at, raw_provider_payload_json
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.local.sha256,
                provider.model_id,
                provider.model_version_id,
                provider.model_name,
                provider.model_type,
                provider.version_name,
                provider.base_model,
                _json_dumps(list(provider.trained_words)),
                _json_dumps(list(provider.tags)),
                provider.description,
                provider.version_description,
                provider.creator_username,
                provider.creator_image,
                _optional_bool_to_int(provider.nsfw),
                _json_dumps(provider.nsfw_level),
                provider.availability,
                _json_dumps(provider.stats),
                provider.model_page_url,
                provider.source_url,
                provider.fetched_at,
                _json_dumps(provider.raw_provider_payload),
            ),
        )
        self._insert_files(connection, record.local.sha256, provider.files)
        self._insert_images(connection, record.local.sha256, provider.images)

    def _insert_files(
        self,
        connection: sqlite3.Connection,
        sha256: str,
        files: Iterable[CivitaiFile],
    ) -> None:
        """Insert CivitAI file rows for one model version."""

        connection.executemany(
            """
            insert into civitai_files(
              sha256, file_id, name, size_kb, primary_file, hashes_json,
              metadata_json
            ) values (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    sha256,
                    file.file_id,
                    file.name,
                    file.size_kb,
                    int(file.primary),
                    _json_dumps(file.hashes),
                    _json_dumps(file.metadata),
                )
                for file in files
            ),
        )

    def _insert_images(
        self,
        connection: sqlite3.Connection,
        sha256: str,
        images: Iterable[CivitaiImage],
    ) -> None:
        """Insert CivitAI image rows for one model version."""

        connection.executemany(
            """
            insert into civitai_images(
              sha256, image_id, url, image_type, nsfw, nsfw_level, width,
              height, meta_json, sort_index
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    sha256,
                    image.image_id,
                    image.url,
                    image.image_type,
                    _optional_bool_to_int(image.nsfw),
                    _json_dumps(image.nsfw_level),
                    image.width,
                    image.height,
                    _json_dumps(image.meta),
                    index,
                )
                for index, image in enumerate(images)
            ),
        )

    def _insert_thumbnail(
        self,
        connection: sqlite3.Connection,
        record: ModelMetadataCacheRecord,
    ) -> None:
        """Insert selected thumbnail source metadata and BLOB variants."""

        assert record.thumbnail is not None
        thumbnail = record.thumbnail
        connection.execute(
            """
            insert into thumbnail_sources(
              sha256, source, selection_policy, source_image_url,
              source_image_id, nsfw, nsfw_level, source_width, source_height,
              downloaded_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.local.sha256,
                thumbnail.source,
                thumbnail.selection_policy,
                thumbnail.source_image_url,
                thumbnail.source_image_id,
                _optional_bool_to_int(thumbnail.nsfw),
                _json_dumps(thumbnail.nsfw_level),
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
                _thumbnail_variant_row(record.local.sha256, variant, assets_by_key)
                for variant in thumbnail.variants
                if variant.storage_key in assets_by_key
            ),
        )

    def _record_from_row(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> ModelMetadataCacheRecord:
        """Reconstruct one domain cache record from normalized SQLite rows."""

        sha256 = str(row["sha256"])
        local = LocalModelEvidence(
            target_id=str(row["target_id"]),
            root_id=str(row["root_id"]),
            relative_path=str(row["relative_path"]),
            kind=str(row["kind"]),
            value=str(row["backend_value"]),
            display_name=str(row["display_name"]),
            size_bytes=int(row["size_bytes"]),
            modified_at=str(row["modified_at"]),
            sha256=sha256,
        )
        provider = self._provider_from_row(connection, sha256)
        thumbnail = self._thumbnail_from_row(connection, sha256)
        return ModelMetadataCacheRecord(
            schema_version=int(row["schema_version"]),
            local=local,
            provider=provider,
            provider_status=str(row["provider_status"]),
            thumbnail=thumbnail,
            thumbnail_status=ThumbnailSelectionStatus(str(row["thumbnail_status"])),
            updated_at=str(row["updated_at"]),
        )

    def _provider_from_row(
        self,
        connection: sqlite3.Connection,
        sha256: str,
    ) -> CivitaiModelVersion | None:
        """Reconstruct normalized CivitAI metadata for one SHA256 key."""

        row = connection.execute(
            "select * from civitai_model_versions where sha256 = ?",
            (sha256,),
        ).fetchone()
        if row is None:
            return None
        files = tuple(
            CivitaiFile(
                file_id=_optional_int(file_row["file_id"]),
                name=str(file_row["name"]),
                size_kb=_optional_float(file_row["size_kb"]),
                file_type=None,
                download_url=None,
                pickle_scan_result=None,
                virus_scan_result=None,
                primary=bool(file_row["primary_file"]),
                hashes=_json_object(file_row["hashes_json"]),
                metadata=_json_object(file_row["metadata_json"]),
            )
            for file_row in connection.execute(
                "select * from civitai_files where sha256 = ? order by id",
                (sha256,),
            ).fetchall()
        )
        images = tuple(
            CivitaiImage(
                image_id=_optional_int(image_row["image_id"]),
                url=str(image_row["url"]),
                image_type=_optional_str(image_row["image_type"]),
                nsfw=_optional_bool_from_int(image_row["nsfw"]),
                nsfw_level=_json_optional_str_int(image_row["nsfw_level"]),
                width=_optional_int(image_row["width"]),
                height=_optional_int(image_row["height"]),
                meta=_optional_json_object(image_row["meta_json"]),
            )
            for image_row in connection.execute(
                """
                select *
                from civitai_images
                where sha256 = ?
                order by sort_index
                """,
                (sha256,),
            ).fetchall()
        )
        return CivitaiModelVersion(
            model_id=int(row["model_id"]),
            model_version_id=int(row["model_version_id"]),
            model_name=str(row["model_name"]),
            model_type=_optional_str(row["model_type"]),
            version_name=str(row["version_name"]),
            base_model=_optional_str(row["base_model"]),
            trained_words=_json_str_tuple(row["trained_words_json"]),
            description=_optional_str(row["description"]),
            version_description=_optional_str(row["version_description"]),
            tags=_json_str_tuple(row["tags_json"]),
            creator_username=_optional_str(row["creator_username"]),
            creator_image=_optional_str(row["creator_image"]),
            nsfw=_optional_bool_from_int(row["nsfw"]),
            nsfw_level=_json_optional_str_int(row["nsfw_level"]),
            availability=_optional_str(row["availability"]),
            files=files,
            images=images,
            stats=_json_object(row["stats_json"]),
            model_page_url=str(row["model_page_url"]),
            source_url=str(row["source_url"]),
            fetched_at=str(row["fetched_at"]),
            raw_provider_payload=_json_object(row["raw_provider_payload_json"]),
        )

    def _thumbnail_from_row(
        self,
        connection: sqlite3.Connection,
        sha256: str,
    ) -> ThumbnailStoreResult | None:
        """Reconstruct selected thumbnail metadata without loading BLOB payloads."""

        row = connection.execute(
            "select * from thumbnail_sources where sha256 = ?",
            (sha256,),
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
                select storage_key, role, size, width, height, content_format, byte_size
                from thumbnail_variants
                where sha256 = ?
                order by role, size
                """,
                (sha256,),
            ).fetchall()
        )
        return ThumbnailStoreResult(
            source=str(row["source"]),
            selection_policy=str(row["selection_policy"]),
            source_image_url=str(row["source_image_url"]),
            source_image_id=_optional_int(row["source_image_id"]),
            nsfw=_optional_bool_from_int(row["nsfw"]),
            nsfw_level=_json_optional_str_int(row["nsfw_level"]),
            source_width=_optional_int(row["source_width"]),
            source_height=_optional_int(row["source_height"]),
            variants=variants,
            downloaded_at=str(row["downloaded_at"]),
        )


def _thumbnail_variant_row(
    sha256: str,
    variant: ThumbnailVariant,
    assets_by_key: dict[str, ThumbnailAsset],
) -> tuple[object, ...]:
    """Return the SQLite row tuple for one thumbnail variant and payload."""

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


def _json_dumps(value: object) -> str:
    """Return compact deterministic JSON for SQLite JSON columns."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _json_loads(value: object) -> object:
    """Return JSON-decoded SQLite text, or ``None`` for absent values."""

    if not isinstance(value, str):
        return None
    return json.loads(value)


def _json_object(value: object) -> JsonObject:
    """Return a JSON object from a SQLite JSON column."""

    parsed = _json_loads(value)
    return cast(JsonObject, parsed if isinstance(parsed, dict) else {})


def _optional_json_object(value: object) -> JsonObject | None:
    """Return a JSON object or ``None`` from a SQLite JSON column."""

    parsed = _json_loads(value)
    return cast(JsonObject | None, parsed if isinstance(parsed, dict) else None)


def _json_str_tuple(value: object) -> tuple[str, ...]:
    """Return string entries from a SQLite JSON array column."""

    parsed = _json_loads(value)
    if not isinstance(parsed, list):
        return ()
    return tuple(item for item in parsed if isinstance(item, str))


def _json_optional_str_int(value: object) -> str | int | None:
    """Return a decoded optional string or integer scalar from JSON text."""

    parsed = _json_loads(value)
    if isinstance(parsed, bool):
        return None
    return parsed if isinstance(parsed, str | int) else None


def _optional_bool_to_int(value: bool | None) -> int | None:
    """Encode an optional boolean as a SQLite integer."""

    return None if value is None else int(value)


def _optional_bool_from_int(value: object) -> bool | None:
    """Decode an optional SQLite integer boolean."""

    if value is None:
        return None
    return bool(value)


def _optional_int(value: object) -> int | None:
    """Return an integer from SQLite when present."""

    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str | bytes | bytearray):
        return int(value)
    raise TypeError(f"Expected integer-compatible SQLite value, got {type(value)!r}.")


def _optional_float(value: object) -> float | None:
    """Return a float from SQLite when present."""

    if value is None:
        return None
    if isinstance(value, int | float | str | bytes | bytearray):
        return float(value)
    raise TypeError(f"Expected float-compatible SQLite value, got {type(value)!r}.")


def _optional_str(value: object) -> str | None:
    """Return a string from SQLite when present."""

    return value if isinstance(value, str) else None


_SCHEMA_SQL = """
create table if not exists metadata_schema (
  key text primary key,
  value text not null
);

create table if not exists model_metadata_records (
  sha256 text primary key,
  target_id text not null,
  root_id text not null,
  relative_path text not null,
  kind text not null,
  backend_value text not null,
  display_name text not null,
  size_bytes integer not null,
  modified_at text not null,
  provider text not null default 'civitai',
  provider_status text not null,
  thumbnail_status text not null,
  thumbnail_policy text not null,
  thumbnail_policy_version integer not null,
  schema_version integer not null,
  updated_at text not null
);

create table if not exists civitai_model_versions (
  sha256 text primary key references model_metadata_records(sha256) on delete cascade,
  model_id integer,
  model_version_id integer,
  model_name text,
  model_type text,
  version_name text,
  base_model text,
  trained_words_json text not null,
  tags_json text not null,
  description text,
  version_description text,
  creator_username text,
  creator_image text,
  nsfw integer,
  nsfw_level text,
  availability text,
  stats_json text not null,
  model_page_url text,
  source_url text,
  fetched_at text,
  raw_provider_payload_json text not null
);

create table if not exists civitai_files (
  id integer primary key autoincrement,
  sha256 text not null references model_metadata_records(sha256) on delete cascade,
  file_id integer,
  name text not null,
  size_kb real,
  primary_file integer not null,
  hashes_json text not null,
  metadata_json text not null
);

create table if not exists civitai_images (
  id integer primary key autoincrement,
  sha256 text not null references model_metadata_records(sha256) on delete cascade,
  image_id integer,
  url text not null,
  image_type text,
  nsfw integer,
  nsfw_level text,
  width integer,
  height integer,
  meta_json text,
  sort_index integer not null
);

create table if not exists thumbnail_sources (
  sha256 text primary key references model_metadata_records(sha256) on delete cascade,
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
  sha256 text not null references model_metadata_records(sha256) on delete cascade,
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

create index if not exists idx_model_metadata_kind
  on model_metadata_records(kind);
create index if not exists idx_model_metadata_relative_path
  on model_metadata_records(relative_path);
create index if not exists idx_model_metadata_kind_relative_path
  on model_metadata_records(kind, relative_path);
create index if not exists idx_civitai_model_base_model
  on civitai_model_versions(base_model);
create index if not exists idx_civitai_files_sha256
  on civitai_files(sha256);
create index if not exists idx_civitai_images_sha256
  on civitai_images(sha256, sort_index);
create index if not exists idx_thumbnail_variants_sha256
  on thumbnail_variants(sha256);
create index if not exists idx_thumbnail_variants_sha256_size
  on thumbnail_variants(sha256, size);
"""


__all__ = ["SqliteModelMetadataStore"]

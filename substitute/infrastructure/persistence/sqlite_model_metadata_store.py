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

"""Persist normalized local and provider model metadata in SQLite."""

from __future__ import annotations

from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
import sqlite3
from typing import Iterator

from substitute.application.cache_lifecycle.cache_ids import CACHE_ID_MODEL_METADATA
from substitute.domain.model_metadata import (
    CivitaiFile,
    CivitaiImage,
    LocalModelEvidence,
    ModelMetadataCacheRecord,
    ThumbnailSelectionStatus,
)
from substitute.domain.model_metadata.thumbnail_policy import FirstSfwThumbnailPolicy
from substitute.infrastructure.persistence.model_metadata_sql_contract import (
    SCHEMA_SQL as _SCHEMA_SQL,
    dump_json as _json_dumps,
    optional_bool_to_int as _optional_bool_to_int,
)
from substitute.infrastructure.persistence.model_metadata_provider_reader import (
    read_provider,
)
from substitute.infrastructure.cache_lifecycle.sqlite_recovery import (
    initialize_recoverable_sqlite,
)

_SCHEMA_VERSION = "3"
_THUMBNAIL_POLICY_VERSION = 3
_DATABASE_NAME = "model_metadata.sqlite3"


class SqliteModelMetadataStore:
    """Own normalized local evidence and provider metadata persistence."""

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
        initialize_recoverable_sqlite(
            self._database_path,
            cache_id=CACHE_ID_MODEL_METADATA,
            initialize=self._create_or_validate_database,
            select_database=self._select_database,
        )

    def _select_database(self, database_path: Path) -> None:
        """Select a recovery database when the invalid file remains locked."""

        self._database_path = database_path

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
            return True

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
        """Persist one enriched provider record without thumbnail binary assets."""

        normalized_record = replace(
            record,
            local=replace(record.local, sha256=record.local.sha256.upper()),
        )
        with self._transaction() as connection:
            self._delete_record(connection, normalized_record.local.sha256)
            self._insert_record(connection, normalized_record)
            if normalized_record.provider is not None:
                self._insert_provider(connection, normalized_record)

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

    def _create_or_validate_database(self) -> None:
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

    def provider_record_count(self) -> int:
        """Return the number of normalized CivitAI provider records."""

        with self._connect() as connection:
            return int(
                connection.execute(
                    "select count(*) as count from civitai_model_versions"
                ).fetchone()["count"]
            )

    def mark_civitai_thumbnails_stale(self) -> None:
        """Mark CivitAI thumbnail selections absent after asset clearing."""

        with self._transaction() as connection:
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
        """Delete provider metadata while preserving local model evidence."""

        with self._transaction() as connection:
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
        provider = read_provider(connection, sha256)
        return ModelMetadataCacheRecord(
            schema_version=int(row["schema_version"]),
            local=local,
            provider=provider,
            provider_status=str(row["provider_status"]),
            thumbnail=None,
            thumbnail_status=ThumbnailSelectionStatus(str(row["thumbnail_status"])),
            updated_at=str(row["updated_at"]),
        )


__all__ = ["SqliteModelMetadataStore"]

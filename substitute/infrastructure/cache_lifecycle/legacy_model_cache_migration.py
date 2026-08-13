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

"""Adopt pre-governance model metadata, thumbnail, and snapshot caches."""

from __future__ import annotations

from pathlib import Path
import json
import shutil
import sqlite3

from substitute.application.cache_lifecycle import PreparedCacheCatalog
from substitute.application.cache_lifecycle.cache_ids import (
    CACHE_ID_MODEL_CATALOG_SNAPSHOTS,
    CACHE_ID_MODEL_METADATA,
    CACHE_ID_MODEL_THUMBNAILS,
)
from substitute.domain.model_metadata import (
    ThumbnailAsset,
    ThumbnailStoreResult,
    ThumbnailVariant,
)
from substitute.infrastructure.cache_lifecycle.legacy_sqlite_validation import (
    sqlite_tables,
    validate_sqlite,
)
from substitute.infrastructure.persistence.sqlite_model_thumbnail_asset_store import (
    SqliteModelThumbnailAssetStore,
)
from substitute.shared.logging.logger import get_logger, log_info

_LOGGER = get_logger("infrastructure.cache_lifecycle.legacy_model_cache_migration")


class LegacyModelCacheMigrator:
    """Split compatible legacy model cache tables among current owners."""

    def __init__(
        self,
        cache_root: Path,
        *,
        installation_root: Path | None,
        legacy_model_metadata_root: Path | None,
    ) -> None:
        """Store every known legacy model cache root."""

        roots = [cache_root / "model_metadata"]
        if legacy_model_metadata_root is not None:
            roots.append(legacy_model_metadata_root)
        if installation_root is not None:
            roots.append(installation_root / "user" / "model_metadata")
        self._legacy_roots = tuple(dict.fromkeys(root.resolve() for root in roots))

    def migrate(self, prepared: PreparedCacheCatalog) -> None:
        """Adopt metadata, thumbnail BLOBs, and snapshots when compatible."""

        prepared_ids = {namespace.cache_id for namespace in prepared.namespaces}
        if CACHE_ID_MODEL_METADATA in prepared_ids:
            self._migrate_metadata_and_thumbnails(
                prepared,
                migrate_thumbnails=CACHE_ID_MODEL_THUMBNAILS in prepared_ids,
            )
        elif CACHE_ID_MODEL_THUMBNAILS in prepared_ids:
            self._migrate_thumbnails_from_legacy_database(prepared)
        if CACHE_ID_MODEL_CATALOG_SNAPSHOTS in prepared_ids:
            self._migrate_snapshots(prepared)

    def _migrate_metadata_and_thumbnails(
        self,
        prepared: PreparedCacheCatalog,
        *,
        migrate_thumbnails: bool,
    ) -> None:
        """Split one schema-3 metadata database into current cache owners."""

        source = _first_existing(self._database_candidates("model_metadata.sqlite3"))
        if source is None:
            return
        validate_sqlite(
            source,
            required_tables={"metadata_schema", "model_metadata_records"},
            schema_table="metadata_schema",
            expected_schema="3",
        )
        destination = (
            prepared.namespace(CACHE_ID_MODEL_METADATA).path / "model_metadata.sqlite3"
        )
        if not destination.exists():
            shutil.copy2(source, destination)
            _log_migration(CACHE_ID_MODEL_METADATA, 1)
        if migrate_thumbnails:
            self._migrate_thumbnails(
                source,
                prepared.namespace(CACHE_ID_MODEL_THUMBNAILS).path,
            )

    def _migrate_thumbnails_from_legacy_database(
        self,
        prepared: PreparedCacheCatalog,
    ) -> None:
        """Adopt thumbnails when their cache owner is prepared independently."""

        source = _first_existing(self._database_candidates("model_metadata.sqlite3"))
        if source is None:
            return
        validate_sqlite(
            source,
            required_tables={"metadata_schema", "model_metadata_records"},
            schema_table="metadata_schema",
            expected_schema="3",
        )
        self._migrate_thumbnails(
            source,
            prepared.namespace(CACHE_ID_MODEL_THUMBNAILS).path,
        )

    def _migrate_thumbnails(self, source: Path, destination: Path) -> None:
        """Adopt thumbnail rows through the current thumbnail-store contract."""

        with sqlite3.connect(source) as connection:
            connection.row_factory = sqlite3.Row
            if not {"thumbnail_sources", "thumbnail_variants"}.issubset(
                sqlite_tables(connection)
            ):
                return
            source_rows = connection.execute(
                "select * from thumbnail_sources"
            ).fetchall()
            variant_rows = connection.execute(
                "select * from thumbnail_variants"
            ).fetchall()
        store = SqliteModelThumbnailAssetStore(destination)
        if store.summary()[0] > 0:
            return
        variants_by_sha: dict[str, list[sqlite3.Row]] = {}
        for row in variant_rows:
            variants_by_sha.setdefault(str(row["sha256"]), []).append(row)
        for row in source_rows:
            sha256 = str(row["sha256"])
            variants, assets = _legacy_thumbnail_variants(
                variants_by_sha.get(sha256, [])
            )
            store.replace(
                sha256,
                ThumbnailStoreResult(
                    source=str(row["source"]),
                    selection_policy=str(row["selection_policy"]),
                    source_image_url=str(row["source_image_url"]),
                    source_image_id=_optional_int(row["source_image_id"]),
                    nsfw=_optional_bool(row["nsfw"]),
                    nsfw_level=_optional_json_scalar(row["nsfw_level"]),
                    source_width=_optional_int(row["source_width"]),
                    source_height=_optional_int(row["source_height"]),
                    variants=variants,
                    downloaded_at=str(row["downloaded_at"]),
                    assets=assets,
                ),
            )
        _log_migration(CACHE_ID_MODEL_THUMBNAILS, len(source_rows))

    def _migrate_snapshots(self, prepared: PreparedCacheCatalog) -> None:
        """Adopt one structurally valid model catalog snapshot database."""

        destination = prepared.namespace(CACHE_ID_MODEL_CATALOG_SNAPSHOTS).path / (
            "model_catalog_snapshots.sqlite3"
        )
        if destination.exists():
            return
        source = _first_existing(
            self._database_candidates("model_catalog_snapshots.sqlite3")
        )
        if source is None:
            return
        validate_sqlite(
            source,
            required_tables={"catalog_snapshots", "catalog_snapshot_items"},
        )
        shutil.copy2(source, destination)
        _log_migration(CACHE_ID_MODEL_CATALOG_SNAPSHOTS, 1)

    def _database_candidates(self, database_name: str) -> tuple[Path, ...]:
        """Return known legacy locations for one model cache database."""

        return tuple(root / database_name for root in self._legacy_roots)


def _legacy_thumbnail_variants(
    rows: list[sqlite3.Row],
) -> tuple[tuple[ThumbnailVariant, ...], tuple[ThumbnailAsset, ...]]:
    """Reconstruct legacy thumbnail references and payloads from database rows."""

    variants = tuple(
        ThumbnailVariant(
            storage_key=str(row["storage_key"]),
            role=str(row["role"]),
            size=int(row["size"]),
            width=int(row["width"]),
            height=int(row["height"]),
            content_format=str(row["content_format"]),
            byte_size=int(row["byte_size"]),
        )
        for row in rows
    )
    assets = tuple(
        ThumbnailAsset(
            storage_key=str(row["storage_key"]),
            width=int(row["width"]),
            height=int(row["height"]),
            qt_format=int(row["qt_format"]),
            bytes_per_line=int(row["bytes_per_line"]),
            content_format=str(row["content_format"]),
            payload=bytes(row["payload"]),
        )
        for row in rows
    )
    return variants, assets


def _first_existing(candidates: tuple[Path, ...]) -> Path | None:
    """Return the first existing legacy candidate."""

    return next((candidate for candidate in candidates if candidate.exists()), None)


def _optional_int(value: object) -> int | None:
    """Return an optional SQLite integer."""

    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str | bytes | bytearray):
        return int(value)
    raise TypeError(f"Expected integer-compatible SQLite value, got {type(value)!r}.")


def _optional_bool(value: object) -> bool | None:
    """Return an optional SQLite boolean."""

    return None if value is None else bool(value)


def _optional_json_scalar(value: object) -> str | int | None:
    """Return an optional string or integer decoded from SQLite JSON text."""

    parsed = json.loads(value) if isinstance(value, str) else None
    if isinstance(parsed, bool):
        return None
    return parsed if isinstance(parsed, str | int) else None


def _log_migration(cache_id: str, migrated_entries: int) -> None:
    """Log a successful nonempty model cache adoption."""

    if migrated_entries > 0:
        log_info(
            _LOGGER,
            "Adopted validated legacy persistent cache content.",
            cache_id=cache_id,
            migrated_entries=migrated_entries,
        )


__all__ = ["LegacyModelCacheMigrator"]

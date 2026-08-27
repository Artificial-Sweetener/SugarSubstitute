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

"""Verify validated legacy cache adoption into governed cache generations."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any

import pytest

from substitute.app.bootstrap.persistent_cache_catalog import (
    CACHE_ID_COMFY_I18N,
    CACHE_ID_CUBE_ICONS,
    CACHE_ID_DANBOORU_IMAGES,
    CACHE_ID_DANBOORU_METADATA,
    CACHE_ID_MODEL_METADATA,
    CACHE_ID_MODEL_THUMBNAILS,
    CACHE_ID_RESTORE_PROJECTION,
    build_persistent_cache_catalog,
)
from substitute.application.cache_lifecycle import (
    PersistentCacheCatalog,
    PreparedCacheCatalog,
)
from substitute.domain.danbooru import (
    DanbooruCachedWikiPage,
    DanbooruLookupStatus,
)
from substitute.domain.model_metadata import (
    LocalModelEvidence,
    ModelMetadataCacheRecord,
    ThumbnailSelectionStatus,
)
from substitute.infrastructure.cache_lifecycle import FilePersistentCacheStorage
from substitute.infrastructure.persistence.danbooru_cache_store import (
    SqliteDanbooruMetadataStore,
)
from substitute.infrastructure.persistence.danbooru_image_cache_store import (
    SqliteDanbooruImageCacheStore,
)
from substitute.infrastructure.persistence.sqlite_cube_icon_cache import (
    SqliteCubeIconCache,
)
from substitute.infrastructure.persistence.sqlite_model_metadata_store import (
    SqliteModelMetadataStore,
)
from substitute.infrastructure.persistence.sqlite_model_thumbnail_asset_store import (
    SqliteModelThumbnailAssetStore,
)


def test_legacy_restore_projection_is_not_adopted_without_producer_proof(
    tmp_path: Path,
) -> None:
    """A 0.19.2 restore cache should remain an intentional cache miss."""

    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    legacy = cache_root / "restore-projection-cache.json"
    legacy.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "app_projection_version": 3,
                "prompt_editor_feature_profile_fingerprint": "legacy",
                "entries": [],
            }
        ),
        encoding="utf-8",
    )

    prepared = _prepare(cache_root, application_version="0.19.2")

    generation = prepared.namespace(CACHE_ID_RESTORE_PROJECTION).path
    assert legacy.is_file()
    assert not (generation / "restore-projection-cache.json").exists()


def test_legacy_comfy_and_danbooru_caches_are_validated_and_split(
    tmp_path: Path,
) -> None:
    """Compatible remote content should survive adoption into cohesive owners."""

    cache_root = tmp_path / "cache"
    comfy_root = cache_root / "comfy_i18n"
    comfy_root.mkdir(parents=True)
    comfy_payload = {
        "schema_version": 2,
        "active_alias": "en",
        "active_node_defs": {"Node": {"display_name": "Node"}},
        "english_node_defs": None,
    }
    (comfy_root / "target.json").write_text(json.dumps(comfy_payload), encoding="utf-8")
    danbooru_root = cache_root / "danbooru"
    metadata = SqliteDanbooruMetadataStore(danbooru_root)
    metadata.save_cached_wiki_page(
        DanbooruCachedWikiPage(
            title="long_hair",
            lookup_status=DanbooruLookupStatus.NOT_FOUND,
            wiki_page=None,
            fetched_at="2026-01-01T00:00:00+00:00",
            expires_at="2026-01-02T00:00:00+00:00",
        )
    )
    image_path = danbooru_root / "danbooru_images" / "preview.jpg"
    image_path.parent.mkdir()
    image_path.write_bytes(b"preview-bytes")
    with sqlite3.connect(danbooru_root / "danbooru_cache.sqlite3") as connection:
        connection.execute(
            """
            create table danbooru_image_assets (
              cache_key text primary key, source_url text not null,
              local_path text not null, rating text, width integer, height integer,
              fetched_at text not null, last_used_at text not null,
              byte_size integer not null default 0
            )
            """
        )
        connection.execute(
            """
            insert into danbooru_image_assets values (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "preview:1",
                "https://example.invalid/preview.jpg",
                str(image_path),
                "s",
                32,
                32,
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
                len(b"preview-bytes"),
            ),
        )

    prepared = _prepare(cache_root)

    assert (
        json.loads(
            (prepared.namespace(CACHE_ID_COMFY_I18N).path / "target.json").read_text(
                encoding="utf-8"
            )
        )
        == comfy_payload
    )
    migrated_metadata = SqliteDanbooruMetadataStore(
        prepared.namespace(CACHE_ID_DANBOORU_METADATA).path
    )
    migrated_images = SqliteDanbooruImageCacheStore(
        prepared.namespace(CACHE_ID_DANBOORU_IMAGES).path
    )
    assert migrated_metadata.load_cached_wiki_page("long_hair") is not None
    migrated_asset = migrated_images.load_cached_image_asset("preview:1")
    assert migrated_asset is not None
    assert migrated_asset.local_path.read_bytes() == b"preview-bytes"


def test_legacy_model_database_splits_thumbnail_assets_from_metadata(
    tmp_path: Path,
) -> None:
    """Legacy model BLOBs should move to the governed thumbnail generation."""

    cache_root = tmp_path / "cache"
    legacy_root = cache_root / "model_metadata"
    metadata = SqliteModelMetadataStore(legacy_root)
    evidence = _local_model_evidence()
    metadata.save_record(
        ModelMetadataCacheRecord(
            schema_version=1,
            local=evidence,
            provider=None,
            provider_status="found",
            thumbnail=None,
            thumbnail_status=ThumbnailSelectionStatus.SELECTED,
            updated_at="2026-01-01T00:00:00+00:00",
        )
    )
    _add_legacy_thumbnail(legacy_root / "model_metadata.sqlite3")

    prepared = _prepare(cache_root)

    migrated_metadata = SqliteModelMetadataStore(
        prepared.namespace(CACHE_ID_MODEL_METADATA).path
    )
    migrated_thumbnails = SqliteModelThumbnailAssetStore(
        prepared.namespace(CACHE_ID_MODEL_THUMBNAILS).path
    )
    assert migrated_metadata.record_for_sha256("ABC123") is not None
    assert migrated_thumbnails.result_for_sha256("ABC123") is not None
    asset = migrated_thumbnails.read_thumbnail_asset("ABC123:standard:1")
    assert asset is not None
    assert asset.payload == b"pixels"


def test_populated_thumbnail_generation_skips_legacy_blob_queries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repeated startup must not reload legacy thumbnail BLOBs after migration."""

    cache_root = tmp_path / "cache"
    legacy_root = cache_root / "model_metadata"
    metadata = SqliteModelMetadataStore(legacy_root)
    metadata.save_record(
        ModelMetadataCacheRecord(
            schema_version=1,
            local=_local_model_evidence(),
            provider=None,
            provider_status="found",
            thumbnail=None,
            thumbnail_status=ThumbnailSelectionStatus.SELECTED,
            updated_at="2026-01-01T00:00:00+00:00",
        )
    )
    legacy_database = legacy_root / "model_metadata.sqlite3"
    _add_legacy_thumbnail(legacy_database)
    _prepare(cache_root)

    real_connect = sqlite3.connect

    def guarded_connect(database: Any, *args: Any, **kwargs: Any) -> Any:
        """Reject legacy thumbnail table scans while allowing metadata validation."""

        connection = real_connect(database, *args, **kwargs)
        if Path(str(database)).resolve() != legacy_database.resolve():
            return connection
        return _LegacyThumbnailQueryGuard(connection)

    monkeypatch.setattr(
        "substitute.infrastructure.cache_lifecycle.legacy_model_cache_migration."
        "sqlite3.connect",
        guarded_connect,
    )

    _prepare(cache_root)


def test_corrupt_legacy_sqlite_is_ignored_without_blocking_preparation(
    tmp_path: Path,
) -> None:
    """Corrupt legacy databases should become empty usable cache generations."""

    cache_root = tmp_path / "cache"
    legacy = cache_root / "cube" / "cube_icon_cache.sqlite3"
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b"not sqlite")

    prepared = _prepare(cache_root)
    cache = SqliteCubeIconCache(prepared.namespace(CACHE_ID_CUBE_ICONS).path)

    assert legacy.read_bytes() == b"not sqlite"
    assert cache.prune(maximum_rows=0, maximum_bytes=0) == 0


def test_legacy_migration_respects_independently_prepared_cache_owners(
    tmp_path: Path,
) -> None:
    """Partial catalogs must not force companion cache namespaces into existence."""

    cache_root = tmp_path / "cache"
    danbooru = SqliteDanbooruMetadataStore(cache_root / "danbooru")
    danbooru.save_cached_wiki_page(
        DanbooruCachedWikiPage(
            title="partial",
            lookup_status=DanbooruLookupStatus.NOT_FOUND,
            wiki_page=None,
            fetched_at="2026-01-01T00:00:00+00:00",
            expires_at="2026-01-02T00:00:00+00:00",
        )
    )
    models = SqliteModelMetadataStore(cache_root / "model_metadata")
    models.save_record(
        ModelMetadataCacheRecord(
            schema_version=1,
            local=_local_model_evidence(),
            provider=None,
            provider_status="found",
            thumbnail=None,
            thumbnail_status=ThumbnailSelectionStatus.SELECTED,
            updated_at="2026-01-01T00:00:00+00:00",
        )
    )

    production = build_persistent_cache_catalog(source_root=Path(__file__).parents[4])
    partial = PersistentCacheCatalog(
        registrations=tuple(
            registration
            for registration in production.registrations
            if registration.cache_id
            in {CACHE_ID_DANBOORU_METADATA, CACHE_ID_MODEL_METADATA}
        )
    )
    prepared = FilePersistentCacheStorage(
        cache_root,
        application_version="current",
        installation_root=cache_root.parent,
        legacy_model_metadata_root=cache_root / "model_metadata",
    ).prepare(partial)

    assert (
        SqliteDanbooruMetadataStore(
            prepared.namespace(CACHE_ID_DANBOORU_METADATA).path
        ).load_cached_wiki_page("partial")
        is not None
    )
    assert (
        SqliteModelMetadataStore(
            prepared.namespace(CACHE_ID_MODEL_METADATA).path
        ).record_for_sha256("ABC123")
        is not None
    )


def _prepare(
    cache_root: Path,
    *,
    application_version: str = "current",
) -> PreparedCacheCatalog:
    """Prepare the production persistent-cache catalog under one test root."""

    catalog = build_persistent_cache_catalog(source_root=Path(__file__).parents[4])
    return FilePersistentCacheStorage(
        cache_root,
        application_version=application_version,
        installation_root=cache_root.parent,
        legacy_model_metadata_root=cache_root / "model_metadata",
    ).prepare(catalog)


def _add_legacy_thumbnail(database_path: Path) -> None:
    """Add one pre-split thumbnail source and BLOB variant to a metadata database."""

    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            create table thumbnail_sources (
              sha256 text primary key, source text not null,
              selection_policy text not null, source_image_url text not null,
              source_image_id integer, nsfw integer, nsfw_level text,
              source_width integer, source_height integer, downloaded_at text not null
            );
            create table thumbnail_variants (
              id integer primary key autoincrement, sha256 text not null,
              storage_key text not null unique, role text not null, size integer not null,
              width integer not null, height integer not null, qt_format integer not null,
              bytes_per_line integer not null, content_format text not null,
              byte_size integer not null, payload blob not null
            );
            """
        )
        connection.execute(
            "insert into thumbnail_sources values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "ABC123",
                "civitai",
                "first-sfw-version-image",
                "https://example.invalid/image.jpg",
                1,
                0,
                '"None"',
                1,
                1,
                "2026-01-01T00:00:00+00:00",
            ),
        )
        connection.execute(
            "insert into thumbnail_variants values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                1,
                "ABC123",
                "ABC123:standard:1",
                "standard",
                1,
                1,
                1,
                6,
                4,
                "test",
                len(b"pixels"),
                b"pixels",
            ),
        )


class _LegacyThumbnailQueryGuard:
    """Proxy a SQLite connection while rejecting expensive legacy BLOB scans."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Store the guarded legacy database connection."""

        object.__setattr__(self, "_connection", connection)

    def __enter__(self) -> _LegacyThumbnailQueryGuard:
        """Enter the underlying connection context and retain the guard."""

        self._connection.__enter__()
        return self

    def __exit__(self, *args: object) -> object:
        """Exit the underlying connection context."""

        return self._connection.__exit__(*args)

    def __getattr__(self, name: str) -> Any:
        """Delegate unguarded connection operations."""

        return getattr(self._connection, name)

    def __setattr__(self, name: str, value: object) -> None:
        """Delegate connection settings such as the row factory."""

        setattr(self._connection, name, value)

    def execute(self, sql: str, *args: Any) -> Any:
        """Reject full reads of legacy thumbnail source and BLOB tables."""

        normalized = " ".join(sql.lower().split())
        if normalized in {
            "select * from thumbnail_sources",
            "select * from thumbnail_variants",
        }:
            raise AssertionError("Repeated startup queried legacy thumbnail BLOBs.")
        return self._connection.execute(sql, *args)


def _local_model_evidence() -> LocalModelEvidence:
    """Return deterministic legacy local model evidence for migration tests."""

    return LocalModelEvidence(
        target_id="target",
        root_id="root",
        relative_path="models/example.safetensors",
        kind="loras",
        value="models/example.safetensors",
        display_name="example",
        size_bytes=10,
        modified_at="2026-01-01T00:00:00+00:00",
        sha256="ABC123",
    )

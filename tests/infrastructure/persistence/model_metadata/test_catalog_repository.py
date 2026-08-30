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

"""Verify durable model-metadata catalog and SQLite repository contracts."""

from __future__ import annotations

from pathlib import Path

from substitute.domain.model_metadata import (
    BANNER_THUMBNAIL_ROLE,
    BANNER_THUMBNAIL_SIZE,
    ModelMetadataCacheRecord,
    STANDARD_THUMBNAIL_ROLE,
    ThumbnailSelectionStatus,
)
from substitute.infrastructure.persistence import (
    JsonModelMetadataCatalogQueryRepository,
    JsonModelMetadataCatalogStore,
)
from tests.infrastructure.persistence.model_metadata.support import (
    evidence,
    provider,
    sqlite_repository,
    thumbnail_result,
)


def test_catalog_store_writes_records_indexes_and_freshness(tmp_path: Path) -> None:
    """SQLite catalog store should atomically persist records under model_metadata."""

    store = sqlite_repository(tmp_path)
    local_evidence = evidence()
    record = ModelMetadataCacheRecord(
        schema_version=1,
        local=local_evidence,
        provider=None,
        provider_status="found",
        thumbnail=thumbnail_result(),
        thumbnail_status=ThumbnailSelectionStatus.SELECTED,
        updated_at="2026-04-14T12:00:00Z",
    )

    assert store.is_fresh(local_evidence) is False
    store.save_record(record)

    records = store.list_records(kind="loras")
    assert records[0].local.relative_path == "models/lora.safetensors"
    assert records[0].thumbnail is not None
    assert [
        (variant.role, variant.size) for variant in records[0].thumbnail.variants
    ] == [
        (BANNER_THUMBNAIL_ROLE, BANNER_THUMBNAIL_SIZE),
        (STANDARD_THUMBNAIL_ROLE, 128),
    ]
    assert records[0].thumbnail.variants[1].storage_key == "ABC123:standard:128"
    assert store.read_thumbnail_asset("ABC123:standard:128") is not None
    assert store.read_thumbnail_asset("ABC123:banner:768x160") is not None
    assert store.is_fresh(local_evidence) is True
    assert (tmp_path / "metadata" / "model_metadata.sqlite3").exists()
    assert (tmp_path / "thumbnails" / "model_thumbnails.sqlite3").exists()


def test_catalog_store_reprocesses_found_records_without_current_thumbnail_policy(
    tmp_path: Path,
) -> None:
    """Found selected-thumbnail records without variants should be refreshed."""

    store = sqlite_repository(tmp_path)
    local_evidence = evidence()
    store.save_record(
        ModelMetadataCacheRecord(
            schema_version=1,
            local=local_evidence,
            provider=None,
            provider_status="found",
            thumbnail=thumbnail_result(include_assets=False),
            thumbnail_status=ThumbnailSelectionStatus.SELECTED,
            updated_at="2026-04-14T12:00:00Z",
        )
    )

    assert store.is_fresh(local_evidence) is False


def test_catalog_store_records_not_found(tmp_path: Path) -> None:
    """Catalog store should keep provider-not-found results fresh."""

    store = sqlite_repository(tmp_path)
    local_evidence = evidence()

    store.save_not_found(local_evidence, fetched_at="2026-04-14T12:00:00Z")

    records = store.list_records(kind="loras")
    assert records[0].provider_status == "not-found"
    assert store.is_fresh(local_evidence) is True


def test_catalog_query_repository_reads_records_from_index(tmp_path: Path) -> None:
    """Catalog query repository should read persisted records through the index."""

    store = sqlite_repository(tmp_path)
    local_evidence = evidence()
    store.save_record(
        ModelMetadataCacheRecord(
            schema_version=1,
            local=local_evidence,
            provider=None,
            provider_status="found",
            thumbnail=thumbnail_result(),
            thumbnail_status=ThumbnailSelectionStatus.SELECTED,
            updated_at="2026-04-14T12:00:00Z",
        )
    )

    records = store.list_records(kind="loras")

    assert len(records) == 1
    assert records[0].local == local_evidence
    assert records[0].thumbnail is not None
    assert records[0].thumbnail.variants[0].role == BANNER_THUMBNAIL_ROLE
    assert records[0].thumbnail.variants[1].storage_key == "ABC123:standard:128"


def test_sqlite_catalog_reads_record_by_sha256(tmp_path: Path) -> None:
    """SQLite catalog should read one cached record by SHA256 for preservation."""

    store = sqlite_repository(tmp_path)
    local_evidence = evidence()
    store.save_record(
        ModelMetadataCacheRecord(
            schema_version=1,
            local=local_evidence,
            provider=provider(),
            provider_status="found",
            thumbnail=thumbnail_result(),
            thumbnail_status=ThumbnailSelectionStatus.SELECTED,
            updated_at="2026-04-14T12:00:00Z",
        )
    )

    record = store.record_for_sha256("abc123")

    assert record is not None
    assert record.local == local_evidence
    assert record.provider is not None
    assert record.thumbnail is not None
    assert record.thumbnail.variants[1].storage_key == "ABC123:standard:128"
    assert store.record_for_sha256("missing") is None


def test_sqlite_catalog_round_trips_civitai_page_and_source_urls(
    tmp_path: Path,
) -> None:
    """SQLite catalog should preserve public and API CivitAI URLs separately."""

    store = sqlite_repository(tmp_path)
    store.save_record(
        ModelMetadataCacheRecord(
            schema_version=1,
            local=evidence(),
            provider=provider(),
            provider_status="found",
            thumbnail=None,
            thumbnail_status=ThumbnailSelectionStatus.NO_SFW_IMAGE,
            updated_at="2026-04-14T12:00:00Z",
        )
    )

    records = store.list_records(kind="loras")

    assert len(records) == 1
    assert records[0].provider is not None
    assert (
        records[0].provider.model_page_url
        == "https://civitai.com/models/100?modelVersionId=200"
    )
    assert (
        records[0].provider.source_url
        == "https://civitai.com/api/v1/model-versions/by-hash/ABC123"
    )


def test_sqlite_clear_civitai_metadata_preserves_local_hash_evidence(
    tmp_path: Path,
) -> None:
    """Clearing provider metadata should not delete local model hash records."""

    store = sqlite_repository(tmp_path)
    local_evidence = evidence()
    store.save_record(
        ModelMetadataCacheRecord(
            schema_version=1,
            local=local_evidence,
            provider=provider(),
            provider_status="found",
            thumbnail=thumbnail_result(),
            thumbnail_status=ThumbnailSelectionStatus.SELECTED,
            updated_at="2026-04-14T12:00:00Z",
        )
    )

    store.clear_civitai_metadata()

    records = store.list_records(kind="loras")
    summary = store.cache_summary()
    assert len(records) == 1
    assert records[0].local == local_evidence
    assert records[0].provider is None
    assert records[0].provider_status == "stale"
    assert records[0].thumbnail is None
    assert summary.provider_record_count == 0
    assert summary.thumbnail_variant_count == 0
    assert store.is_fresh(local_evidence) is False


def test_sqlite_save_local_evidence_preserves_hash_for_resolution(
    tmp_path: Path,
) -> None:
    """Downloaded model evidence should be queryable without provider metadata."""

    store = sqlite_repository(tmp_path)
    local_evidence = evidence()

    store.save_local_evidence(local_evidence, updated_at="2026-05-21T00:00:00Z")

    records = store.list_records(kind="loras")
    assert len(records) == 1
    assert records[0].local == local_evidence
    assert records[0].provider is None
    assert records[0].provider_status == "stale"
    assert store.is_fresh(local_evidence) is False


def test_json_catalog_round_trips_civitai_page_and_source_urls(
    tmp_path: Path,
) -> None:
    """JSON catalog should preserve public and API CivitAI URLs separately."""

    store = JsonModelMetadataCatalogStore(tmp_path)
    store.save_record(
        ModelMetadataCacheRecord(
            schema_version=1,
            local=evidence(),
            provider=provider(),
            provider_status="found",
            thumbnail=None,
            thumbnail_status=ThumbnailSelectionStatus.NO_SFW_IMAGE,
            updated_at="2026-04-14T12:00:00Z",
        )
    )
    query = JsonModelMetadataCatalogQueryRepository(tmp_path)

    records = query.list_records(kind="loras")

    assert len(records) == 1
    assert records[0].provider is not None
    assert (
        records[0].provider.model_page_url
        == "https://civitai.com/models/100?modelVersionId=200"
    )
    assert (
        records[0].provider.source_url
        == "https://civitai.com/api/v1/model-versions/by-hash/ABC123"
    )


def test_thumbnail_asset_repository_returns_none_for_missing_asset(
    tmp_path: Path,
) -> None:
    """SQLite thumbnail asset repository should return ``None`` for missing keys."""

    store = sqlite_repository(tmp_path)

    assert store.read_thumbnail_asset("missing") is None

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

"""Tests for model metadata persistence stores."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from PySide6.QtCore import QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QColor, QImage

from substitute.domain.model_metadata import (
    BANNER_THUMBNAIL_HEIGHT,
    BANNER_THUMBNAIL_ROLE,
    BANNER_THUMBNAIL_SIZE,
    BANNER_THUMBNAIL_WIDTH,
    CivitaiImage,
    CivitaiModelVersion,
    LocalModelEvidence,
    ModelMetadataCacheRecord,
    STANDARD_THUMBNAIL_ROLE,
    ThumbnailSelectionStatus,
    ThumbnailAsset,
    ThumbnailStoreResult,
    ThumbnailVariant,
)
from substitute.infrastructure.persistence import (
    JsonModelMetadataCatalogQueryRepository,
    JsonModelMetadataCatalogStore,
    ModelThumbnailStore,
    SqliteModelMetadataStore,
)
from substitute.shared.qt_thumbnail_codec import (
    image_from_qt_thumbnail_payload,
    prepare_qt_thumbnail,
)


class _FakeImageResponse:
    """Provide a thumbnail download response for store tests."""

    def __init__(
        self,
        *,
        content_type: str,
        content: bytes | None = None,
    ) -> None:
        self.headers = {"Content-Type": content_type}
        self.content = content if content is not None else _encoded_image_bytes()

    def raise_for_status(self) -> None:
        """Accept successful responses."""


def test_catalog_store_writes_records_indexes_and_freshness(tmp_path: Path) -> None:
    """SQLite catalog store should atomically persist records under model_metadata."""

    store = SqliteModelMetadataStore(tmp_path)
    evidence = _evidence()
    record = ModelMetadataCacheRecord(
        schema_version=1,
        local=evidence,
        provider=None,
        provider_status="found",
        thumbnail=_thumbnail_result(),
        thumbnail_status=ThumbnailSelectionStatus.SELECTED,
        updated_at="2026-04-14T12:00:00Z",
    )

    assert store.is_fresh(evidence) is False
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
    assert store.is_fresh(evidence) is True
    assert (tmp_path / "model_metadata.sqlite3").exists()


def test_catalog_store_reprocesses_found_records_without_current_thumbnail_policy(
    tmp_path: Path,
) -> None:
    """Found selected-thumbnail records without variants should be refreshed."""

    store = SqliteModelMetadataStore(tmp_path)
    evidence = _evidence()
    store.save_record(
        ModelMetadataCacheRecord(
            schema_version=1,
            local=evidence,
            provider=None,
            provider_status="found",
            thumbnail=_thumbnail_result(include_assets=False),
            thumbnail_status=ThumbnailSelectionStatus.SELECTED,
            updated_at="2026-04-14T12:00:00Z",
        )
    )

    assert store.is_fresh(evidence) is False


def test_catalog_store_records_not_found(tmp_path: Path) -> None:
    """Catalog store should keep provider-not-found results fresh."""

    store = SqliteModelMetadataStore(tmp_path)
    evidence = _evidence()

    store.save_not_found(evidence, fetched_at="2026-04-14T12:00:00Z")

    records = store.list_records(kind="loras")
    assert records[0].provider_status == "not-found"
    assert store.is_fresh(evidence) is True


def test_catalog_query_repository_reads_records_from_index(tmp_path: Path) -> None:
    """Catalog query repository should read persisted records through the index."""

    store = SqliteModelMetadataStore(tmp_path)
    evidence = _evidence()
    store.save_record(
        ModelMetadataCacheRecord(
            schema_version=1,
            local=evidence,
            provider=None,
            provider_status="found",
            thumbnail=_thumbnail_result(),
            thumbnail_status=ThumbnailSelectionStatus.SELECTED,
            updated_at="2026-04-14T12:00:00Z",
        )
    )

    records = store.list_records(kind="loras")

    assert len(records) == 1
    assert records[0].local == evidence
    assert records[0].thumbnail is not None
    assert records[0].thumbnail.variants[0].role == BANNER_THUMBNAIL_ROLE
    assert records[0].thumbnail.variants[1].storage_key == "ABC123:standard:128"


def test_sqlite_catalog_reads_record_by_sha256(tmp_path: Path) -> None:
    """SQLite catalog should read one cached record by SHA256 for preservation."""

    store = SqliteModelMetadataStore(tmp_path)
    evidence = _evidence()
    store.save_record(
        ModelMetadataCacheRecord(
            schema_version=1,
            local=evidence,
            provider=_provider(),
            provider_status="found",
            thumbnail=_thumbnail_result(),
            thumbnail_status=ThumbnailSelectionStatus.SELECTED,
            updated_at="2026-04-14T12:00:00Z",
        )
    )

    record = store.record_for_sha256("abc123")

    assert record is not None
    assert record.local == evidence
    assert record.provider is not None
    assert record.thumbnail is not None
    assert record.thumbnail.variants[1].storage_key == "ABC123:standard:128"
    assert store.record_for_sha256("missing") is None


def test_sqlite_catalog_round_trips_civitai_page_and_source_urls(
    tmp_path: Path,
) -> None:
    """SQLite catalog should preserve public and API CivitAI URLs separately."""

    store = SqliteModelMetadataStore(tmp_path)
    store.save_record(
        ModelMetadataCacheRecord(
            schema_version=1,
            local=_evidence(),
            provider=_provider(),
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

    store = SqliteModelMetadataStore(tmp_path)
    evidence = _evidence()
    store.save_record(
        ModelMetadataCacheRecord(
            schema_version=1,
            local=evidence,
            provider=_provider(),
            provider_status="found",
            thumbnail=_thumbnail_result(),
            thumbnail_status=ThumbnailSelectionStatus.SELECTED,
            updated_at="2026-04-14T12:00:00Z",
        )
    )

    store.clear_civitai_metadata()

    records = store.list_records(kind="loras")
    summary = store.cache_summary()
    assert len(records) == 1
    assert records[0].local == evidence
    assert records[0].provider is None
    assert records[0].provider_status == "stale"
    assert records[0].thumbnail is None
    assert summary.provider_record_count == 0
    assert summary.thumbnail_variant_count == 0
    assert store.is_fresh(evidence) is False


def test_sqlite_save_local_evidence_preserves_hash_for_resolution(
    tmp_path: Path,
) -> None:
    """Downloaded model evidence should be queryable without provider metadata."""

    store = SqliteModelMetadataStore(tmp_path)
    evidence = _evidence()

    store.save_local_evidence(evidence, updated_at="2026-05-21T00:00:00Z")

    records = store.list_records(kind="loras")
    assert len(records) == 1
    assert records[0].local == evidence
    assert records[0].provider is None
    assert records[0].provider_status == "stale"
    assert store.is_fresh(evidence) is False


def test_json_catalog_round_trips_civitai_page_and_source_urls(
    tmp_path: Path,
) -> None:
    """JSON catalog should preserve public and API CivitAI URLs separately."""

    store = JsonModelMetadataCatalogStore(tmp_path)
    store.save_record(
        ModelMetadataCacheRecord(
            schema_version=1,
            local=_evidence(),
            provider=_provider(),
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

    store = SqliteModelMetadataStore(tmp_path)

    assert store.read_thumbnail_asset("missing") is None


def test_thumbnail_store_writes_images_and_rejects_non_images(tmp_path: Path) -> None:
    """Thumbnail store should download only image content."""

    calls: list[str] = []

    def fake_get(url: str, **_kwargs: object) -> _FakeImageResponse:
        """Return fake image or text responses by URL."""

        calls.append(url)
        if url.endswith(".txt"):
            return _FakeImageResponse(content_type="text/plain", content=b"text")
        return _FakeImageResponse(content_type="image/jpeg")

    store = ModelThumbnailStore(
        tmp_path,
        http_get=fake_get,
        clock=lambda: "2026-04-14T12:00:00Z",
    )

    cached = store.cache_thumbnail(
        sha256="abc123",
        image=_image("https://image.example/safe.jpg"),
        selection_policy="first-sfw-version-image",
    )
    rejected = store.cache_thumbnail(
        sha256="def456",
        image=_image("https://image.example/not-image.txt"),
        selection_policy="first-sfw-version-image",
    )

    assert cached is not None
    assert [(variant.role, variant.size) for variant in cached.variants] == [
        (STANDARD_THUMBNAIL_ROLE, 128),
        (STANDARD_THUMBNAIL_ROLE, 256),
        (STANDARD_THUMBNAIL_ROLE, 512),
        (BANNER_THUMBNAIL_ROLE, BANNER_THUMBNAIL_SIZE),
    ]
    assert cached.variants[0].storage_key == "ABC123:standard:128"
    assert cached.variants[0].width == 85
    assert cached.variants[0].height == 128
    assert cached.variants[-1].storage_key == "ABC123:banner:768x160"
    assert cached.variants[-1].width == BANNER_THUMBNAIL_WIDTH
    assert cached.variants[-1].height == BANNER_THUMBNAIL_HEIGHT
    assert _image_from_asset(cached.assets[0]) is not None
    assert _image_from_asset(cached.assets[-1]) is not None
    assert rejected is None
    assert calls == [
        "https://image.example/safe.jpg",
        "https://image.example/not-image.txt",
    ]


def test_thumbnail_store_caches_local_output_thumbnail(tmp_path: Path) -> None:
    """Thumbnail store should prepare standard and banner variants from a local image."""

    store = ModelThumbnailStore(
        tmp_path,
        clock=lambda: "2026-07-03T12:00:00Z",
    )
    image = QImage(96, 64, QImage.Format.Format_ARGB32)
    image.fill(QColor("#336699"))

    cached = store.cache_local_thumbnail(
        sha256="abc123",
        image=image,
        source="output_canvas",
        source_label="C:/outputs/image.png",
    )

    assert cached is not None
    assert cached.source == "output_canvas"
    assert cached.selection_policy == "user_selected_output_canvas"
    assert cached.source_image_url == "C:/outputs/image.png"
    assert cached.source_image_id is None
    assert cached.variants[0].storage_key == "ABC123:standard:128"
    assert cached.variants[-1].storage_key == "ABC123:banner:768x160"
    assert _image_from_asset(cached.assets[0]) is not None
    assert _image_from_asset(cached.assets[-1]) is not None


def test_thumbnail_store_rejects_null_local_output_thumbnail(tmp_path: Path) -> None:
    """Thumbnail store should reject null local images."""

    store = ModelThumbnailStore(tmp_path)

    rejected = store.cache_local_thumbnail(
        sha256="abc123",
        image=QImage(),
        source="output_canvas",
        source_label="C:/outputs/missing.png",
    )

    assert rejected is None


def test_thumbnail_store_accepts_image_url_when_content_type_is_missing(
    tmp_path: Path,
) -> None:
    """Thumbnail store should accept CivitAI image URLs when headers omit content type."""

    def fake_get(_url: str, **_kwargs: object) -> _FakeImageResponse:
        """Return a response with a missing content type."""

        return _FakeImageResponse(content_type="")

    store = ModelThumbnailStore(
        tmp_path,
        http_get=fake_get,
        clock=lambda: "2026-04-14T12:00:00Z",
    )

    cached = store.cache_thumbnail(
        sha256="abc123",
        image=_image(
            "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/example/original=true/87798219.jpeg"
        ),
        selection_policy="first-sfw-version-image",
    )

    assert cached is not None
    assert cached.variants[0].storage_key == "ABC123:standard:128"
    assert _image_from_asset(cached.assets[0]) is not None


def test_thumbnail_store_accepts_octet_stream_when_payload_decodes(
    tmp_path: Path,
) -> None:
    """Thumbnail store should accept CivitAI images served as octet streams."""

    def fake_get(_url: str, **_kwargs: object) -> _FakeImageResponse:
        """Return a decodable image response with a generic binary content type."""

        return _FakeImageResponse(content_type="binary/octet-stream")

    store = ModelThumbnailStore(
        tmp_path,
        http_get=fake_get,
        clock=lambda: "2026-04-14T12:00:00Z",
    )

    cached = store.cache_thumbnail(
        sha256="abc123",
        image=_image(
            "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/example/original=true/39128512.jpeg"
        ),
        selection_policy="first-sfw-version-image",
    )

    assert cached is not None
    assert cached.variants[0].storage_key == "ABC123:standard:128"
    assert _image_from_asset(cached.assets[0]) is not None


def test_thumbnail_store_accepts_text_plain_when_payload_decodes(
    tmp_path: Path,
) -> None:
    """Thumbnail store should accept CivitAI images served with text headers."""

    def fake_get(_url: str, **_kwargs: object) -> _FakeImageResponse:
        """Return a decodable image response with a misleading text content type."""

        return _FakeImageResponse(content_type="text/plain")

    store = ModelThumbnailStore(
        tmp_path,
        http_get=fake_get,
        clock=lambda: "2026-04-14T12:00:00Z",
    )

    cached = store.cache_thumbnail(
        sha256="abc123",
        image=_image(
            "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/example/original=true/461741.jpeg"
        ),
        selection_policy="first-sfw-version-image",
    )

    assert cached is not None
    assert cached.variants[0].storage_key == "ABC123:standard:128"
    assert _image_from_asset(cached.assets[0]) is not None


def test_thumbnail_store_rejects_text_plain_when_payload_does_not_decode(
    tmp_path: Path,
) -> None:
    """Thumbnail store should reject mislabeled payloads that are not images."""

    def fake_get(_url: str, **_kwargs: object) -> _FakeImageResponse:
        """Return an undecodable payload with a text content type."""

        return _FakeImageResponse(content_type="text/plain", content=b"text")

    store = ModelThumbnailStore(
        tmp_path,
        http_get=fake_get,
        clock=lambda: "2026-04-14T12:00:00Z",
    )

    rejected = store.cache_thumbnail(
        sha256="abc123",
        image=_image("https://image.civitai.com/not-an-image.txt"),
        selection_policy="first-sfw-version-image",
    )

    assert rejected is None


def _evidence() -> LocalModelEvidence:
    """Return one local model evidence record."""

    return LocalModelEvidence(
        target_id="target-1",
        root_id="root-1",
        relative_path="models/lora.safetensors",
        kind="loras",
        value="models/lora.safetensors",
        display_name="lora",
        size_bytes=123,
        modified_at="2026-04-14T01:00:00Z",
        sha256="ABC123",
    )


def _thumbnail_result(*, include_assets: bool = True) -> ThumbnailStoreResult:
    """Return one cached thumbnail result."""

    asset = _thumbnail_asset("ABC123:standard:128", width=85, height=128)
    banner_asset = _thumbnail_asset(
        "ABC123:banner:768x160",
        width=BANNER_THUMBNAIL_WIDTH,
        height=BANNER_THUMBNAIL_HEIGHT,
    )
    return ThumbnailStoreResult(
        source="civitai",
        selection_policy="first-sfw-version-image",
        source_image_url="https://image.example/safe.jpg",
        source_image_id=1,
        nsfw=False,
        nsfw_level="None",
        source_width=512,
        source_height=768,
        variants=(
            ThumbnailVariant(
                size=128,
                storage_key="ABC123:standard:128",
                width=85,
                height=128,
                content_format="sqthumb-qimage-argb32-premultiplied",
                byte_size=len(asset.payload),
                role=STANDARD_THUMBNAIL_ROLE,
            ),
            ThumbnailVariant(
                size=BANNER_THUMBNAIL_SIZE,
                storage_key="ABC123:banner:768x160",
                width=BANNER_THUMBNAIL_WIDTH,
                height=BANNER_THUMBNAIL_HEIGHT,
                content_format="sqthumb-qimage-argb32-premultiplied",
                byte_size=len(banner_asset.payload),
                role=BANNER_THUMBNAIL_ROLE,
            ),
        ),
        downloaded_at="2026-04-14T12:00:00Z",
        assets=(asset, banner_asset) if include_assets else (),
    )


def _provider() -> CivitaiModelVersion:
    """Return one normalized CivitAI provider record."""

    return CivitaiModelVersion(
        model_id=100,
        model_version_id=200,
        model_name="Model ABC123",
        model_type="LORA",
        version_name="Version A",
        base_model="SDXL 1.0",
        trained_words=("trigger",),
        description=None,
        version_description=None,
        tags=("portrait",),
        creator_username=None,
        creator_image=None,
        nsfw=False,
        nsfw_level="None",
        availability=None,
        files=(),
        images=(),
        stats={"downloadCount": 5},
        model_page_url="https://civitai.com/models/100?modelVersionId=200",
        source_url="https://civitai.com/api/v1/model-versions/by-hash/ABC123",
        fetched_at="2026-04-14T12:00:00Z",
        raw_provider_payload={"id": 200},
    )


def _thumbnail_asset(storage_key: str, *, width: int, height: int) -> ThumbnailAsset:
    """Return one valid thumbnail asset for persistence tests."""

    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("red"))
    prepared = prepare_qt_thumbnail(image)
    return ThumbnailAsset(
        storage_key=storage_key,
        width=prepared.width,
        height=prepared.height,
        qt_format=prepared.qt_format,
        bytes_per_line=prepared.bytes_per_line,
        content_format=prepared.content_format,
        payload=prepared.payload,
    )


def _image_from_asset(asset: ThumbnailAsset) -> QImage | None:
    """Return one QImage from a test thumbnail asset."""

    return image_from_qt_thumbnail_payload(
        width=asset.width,
        height=asset.height,
        qt_format=asset.qt_format,
        bytes_per_line=asset.bytes_per_line,
        payload=asset.payload,
    )


def _image(url: str) -> CivitaiImage:
    """Return one selected CivitAI image."""

    return CivitaiImage(
        image_id=1,
        url=url,
        image_type="image",
        nsfw=False,
        nsfw_level="None",
        width=512,
        height=768,
        meta=None,
    )


def _encoded_image_bytes() -> bytes:
    """Return a small valid JPEG payload for thumbnail-store tests."""

    image = QImage(16, 24, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    payload = QByteArray()
    buffer = QBuffer(payload)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    cast(Any, image).save(buffer, "JPG")
    buffer.close()
    return bytes(payload.data())

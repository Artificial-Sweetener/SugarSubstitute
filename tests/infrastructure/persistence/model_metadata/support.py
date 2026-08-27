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

"""Provide deterministic model-metadata persistence test fixtures."""

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
    STANDARD_THUMBNAIL_ROLE,
    ThumbnailAsset,
    ThumbnailStoreResult,
    ThumbnailVariant,
)
from substitute.infrastructure.persistence import (
    ComposedModelMetadataRepository,
    SqliteModelMetadataStore,
    SqliteModelThumbnailAssetStore,
)
from substitute.shared.qt_thumbnail_codec import (
    image_from_qt_thumbnail_payload,
    prepare_qt_thumbnail,
)


class FakeImageResponse:
    """Provide one deterministic thumbnail-download response."""

    def __init__(
        self,
        *,
        content_type: str,
        content: bytes | None = None,
    ) -> None:
        """Store headers and a valid image payload unless overridden."""

        self.headers = {"Content-Type": content_type}
        self.content = content if content is not None else encoded_image_bytes()

    def raise_for_status(self) -> None:
        """Accept the synthetic successful response."""


def evidence() -> LocalModelEvidence:
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


def sqlite_repository(cache_root: Path) -> ComposedModelMetadataRepository:
    """Return model metadata and thumbnail stores with separate cache roots."""

    return ComposedModelMetadataRepository(
        metadata=SqliteModelMetadataStore(cache_root / "metadata"),
        thumbnails=SqliteModelThumbnailAssetStore(cache_root / "thumbnails"),
    )


def thumbnail_result(*, include_assets: bool = True) -> ThumbnailStoreResult:
    """Return one cached thumbnail result."""

    asset = thumbnail_asset("ABC123:standard:128", width=85, height=128)
    banner_asset = thumbnail_asset(
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


def provider() -> CivitaiModelVersion:
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


def thumbnail_asset(storage_key: str, *, width: int, height: int) -> ThumbnailAsset:
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


def image_from_asset(asset: ThumbnailAsset) -> QImage | None:
    """Return one QImage from a test thumbnail asset."""

    return image_from_qt_thumbnail_payload(
        width=asset.width,
        height=asset.height,
        qt_format=asset.qt_format,
        bytes_per_line=asset.bytes_per_line,
        payload=asset.payload,
    )


def image(url: str) -> CivitaiImage:
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


def encoded_image_bytes() -> bytes:
    """Return a small valid JPEG payload for thumbnail-store tests."""

    image = QImage(16, 24, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    payload = QByteArray()
    buffer = QBuffer(payload)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    cast(Any, image).save(buffer, "JPG")
    buffer.close()
    return bytes(payload.data())

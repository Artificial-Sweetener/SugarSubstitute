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

"""Download and persist selected CivitAI images as Qt-ready thumbnails."""

from __future__ import annotations

from collections.abc import Callable
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

from substitute.domain.model_metadata import (
    BANNER_THUMBNAIL_HEIGHT,
    BANNER_THUMBNAIL_ROLE,
    BANNER_THUMBNAIL_SIZE,
    BANNER_THUMBNAIL_WIDTH,
    CivitaiImage,
    STANDARD_THUMBNAIL_ROLE,
    ThumbnailAsset,
    ThumbnailStoreResult,
    ThumbnailVariant,
)
from substitute.shared.qt_thumbnail_codec import prepare_qt_thumbnail
from substitute.shared.logging.logger import get_logger, log_debug, log_warning
from sugarsubstitute_shared.windows_long_paths import qt_filesystem_path

from .thumbnail_banner_cropper import ThumbnailBannerCropper

_LOGGER = get_logger("infrastructure.persistence.model_thumbnail_store")
HttpGet = Callable[..., Any]


class ModelThumbnailStore:
    """Download selected model thumbnails and prepare Qt-ready variants."""

    def __init__(
        self,
        model_metadata_root: Path,
        *,
        http_get: HttpGet = requests.get,
        timeout_seconds: float = 20.0,
        variant_sizes: tuple[int, ...] = (128, 256, 512),
        banner_cropper: ThumbnailBannerCropper | None = None,
        clock: Callable[[], str] | None = None,
    ) -> None:
        """Initialize the thumbnail preparer."""

        self._root = model_metadata_root.resolve()
        self._http_get = http_get
        self._timeout_seconds = timeout_seconds
        self._variant_sizes = variant_sizes or (128, 256, 512)
        self._banner_cropper = banner_cropper or ThumbnailBannerCropper()
        self._clock = clock or _utc_now
        self._unavailable_remote_image_urls: set[str] = set()

    def cache_thumbnail(
        self,
        *,
        sha256: str,
        image: CivitaiImage,
        selection_policy: str,
    ) -> ThumbnailStoreResult | None:
        """Download and cache one selected CivitAI thumbnail image."""

        normalized_sha256 = sha256.upper()
        if not self._begin_remote_image_download(image.url):
            return None
        try:
            response = self._http_get(image.url, timeout=self._timeout_seconds)
            response.raise_for_status()
        except requests.RequestException as error:
            self._finish_remote_image_download(
                image.url,
                unavailable=_is_not_found_response(error),
            )
            log_warning(
                _LOGGER,
                "Failed to download CivitAI thumbnail",
                sha256=normalized_sha256,
                image_url=image.url,
                error=repr(error),
            )
            return None
        self._finish_remote_image_download(image.url, unavailable=False)
        content_type = _read_content_type(response)
        source_image = QImage.fromData(bytes(response.content))
        if source_image.isNull():
            log_warning(
                _LOGGER,
                "Rejected undecodable CivitAI thumbnail response",
                sha256=normalized_sha256,
                image_url=image.url,
                content_type=content_type,
            )
            return None

        variants: list[ThumbnailVariant] = []
        assets: list[ThumbnailAsset] = []
        for size in self._variant_sizes:
            storage_key = f"{normalized_sha256}:{STANDARD_THUMBNAIL_ROLE}:{size}"
            asset, variant = _prepared_thumbnail_variant(
                storage_key=storage_key,
                role=STANDARD_THUMBNAIL_ROLE,
                size=size,
                image=_max_edge_thumbnail(source_image, size),
            )
            assets.append(asset)
            variants.append(variant)
        banner = _prepared_banner_variant(
            self._banner_cropper,
            source_image,
            normalized_sha256,
            image_url=image.url,
        )
        if banner is not None:
            asset, variant = banner
            assets.append(asset)
            variants.append(variant)
        return ThumbnailStoreResult(
            source="civitai",
            selection_policy=selection_policy,
            source_image_url=image.url,
            source_image_id=image.image_id,
            nsfw=image.nsfw,
            nsfw_level=image.nsfw_level,
            source_width=image.width,
            source_height=image.height,
            variants=tuple(variants),
            downloaded_at=self._clock(),
            assets=tuple(assets),
        )

    def _begin_remote_image_download(self, image_url: str) -> bool:
        """Allow a remote image URL unless its current session marked it unavailable."""

        if image_url in self._unavailable_remote_image_urls:
            log_debug(
                _LOGGER,
                "Skipped unavailable CivitAI thumbnail URL",
                image_url=image_url,
            )
            return False
        return True

    def _finish_remote_image_download(
        self,
        image_url: str,
        *,
        unavailable: bool,
    ) -> None:
        """Retain definitive unavailable remote image URLs for this app session."""

        if unavailable:
            self._unavailable_remote_image_urls.add(image_url)

    def cache_local_thumbnail(
        self,
        *,
        sha256: str,
        image: object | None,
        source: str,
        source_label: str,
        source_path: str | None = None,
        source_width: int | None = None,
        source_height: int | None = None,
    ) -> ThumbnailStoreResult | None:
        """Cache a local image as the selected thumbnail for one model."""

        normalized_sha256 = sha256.upper()
        source_image = _qimage_from_local_payload(image, source_path)
        if source_image is None or source_image.isNull():
            log_warning(
                _LOGGER,
                "Rejected null local model thumbnail image",
                sha256=normalized_sha256,
                source=source,
                source_label=source_label,
                source_path=source_path,
            )
            return None
        width = source_width if source_width is not None else source_image.width()
        height = source_height if source_height is not None else source_image.height()
        variants: list[ThumbnailVariant] = []
        assets: list[ThumbnailAsset] = []
        for size in self._variant_sizes:
            storage_key = f"{normalized_sha256}:{STANDARD_THUMBNAIL_ROLE}:{size}"
            asset, variant = _prepared_thumbnail_variant(
                storage_key=storage_key,
                role=STANDARD_THUMBNAIL_ROLE,
                size=size,
                image=_max_edge_thumbnail(source_image, size),
            )
            assets.append(asset)
            variants.append(variant)
        banner = _prepared_banner_variant(
            self._banner_cropper,
            source_image,
            normalized_sha256,
            image_url=source_label,
        )
        if banner is not None:
            asset, variant = banner
            assets.append(asset)
            variants.append(variant)
        return ThumbnailStoreResult(
            source=source,
            selection_policy="user_selected_output_canvas",
            source_image_url=source_label,
            source_image_id=None,
            nsfw=None,
            nsfw_level=None,
            source_width=width,
            source_height=height,
            variants=tuple(variants),
            downloaded_at=self._clock(),
            assets=tuple(assets),
        )


def _is_not_found_response(error: requests.RequestException) -> bool:
    """Return whether a request failure represents a definitive missing image URL."""

    response = getattr(error, "response", None)
    return getattr(response, "status_code", None) == 404


def _prepared_banner_variant(
    cropper: ThumbnailBannerCropper,
    source_image: QImage,
    sha256: str,
    *,
    image_url: str,
) -> tuple[ThumbnailAsset, ThumbnailVariant] | None:
    """Return the prepared banner asset and variant, or ``None`` on failure."""

    storage_key = (
        f"{sha256}:{BANNER_THUMBNAIL_ROLE}:"
        f"{BANNER_THUMBNAIL_WIDTH}x{BANNER_THUMBNAIL_HEIGHT}"
    )
    try:
        banner = cropper.crop_banner(source_image)
    except Exception as error:
        log_warning(
            _LOGGER,
            "Failed to generate CivitAI thumbnail banner variant",
            sha256=sha256,
            image_url=image_url,
            error=repr(error),
        )
        return None
    return _prepared_thumbnail_variant(
        storage_key=storage_key,
        role=BANNER_THUMBNAIL_ROLE,
        size=BANNER_THUMBNAIL_SIZE,
        image=banner.image,
    )


def _prepared_thumbnail_variant(
    *,
    storage_key: str,
    role: str,
    size: int,
    image: QImage,
) -> tuple[ThumbnailAsset, ThumbnailVariant]:
    """Prepare one Qt-ready thumbnail asset and matching variant metadata."""

    prepared = prepare_qt_thumbnail(image)
    asset = ThumbnailAsset(
        storage_key=storage_key,
        width=prepared.width,
        height=prepared.height,
        qt_format=prepared.qt_format,
        bytes_per_line=prepared.bytes_per_line,
        content_format=prepared.content_format,
        payload=prepared.payload,
    )
    variant = ThumbnailVariant(
        size=size,
        storage_key=storage_key,
        width=asset.width,
        height=asset.height,
        content_format=asset.content_format,
        byte_size=len(asset.payload),
        role=role,
    )
    return asset, variant


def _read_content_type(response: Any) -> str:
    """Return a lowercase response content type without parameters."""

    headers = getattr(response, "headers", {})
    raw_content_type = ""
    if isinstance(headers, Mapping):
        value = headers.get("content-type") or headers.get("Content-Type")
        raw_content_type = value if isinstance(value, str) else ""
    return raw_content_type.split(";", maxsplit=1)[0].strip().lower()


def _qimage_from_local_payload(
    payload: object | None,
    source_path: str | None,
) -> QImage | None:
    """Return a detached QImage from a local payload or path."""

    if isinstance(payload, QImage):
        return payload.copy()
    if isinstance(payload, bytes | bytearray | memoryview):
        image = QImage.fromData(bytes(payload))
        if not image.isNull():
            return image.copy()
    if source_path:
        image = QImage(qt_filesystem_path(source_path))
        if not image.isNull():
            return image.copy()
    return None


def _max_edge_thumbnail(source_image: QImage, size: int) -> QImage:
    """Return an aspect-preserving thumbnail whose longest edge matches ``size``."""

    return source_image.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def _utc_now() -> str:
    """Return the current UTC timestamp for cache records."""

    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


__all__ = ["ModelThumbnailStore"]

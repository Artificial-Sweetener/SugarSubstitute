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

"""Cache prepared Qt pixmaps for reusable media wall thumbnail painting."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QPixmap

from substitute.application.model_metadata import ThumbnailAssetRepository
from substitute.presentation.widgets.media_wall.media_wall_item import (
    ThumbnailVariantReference,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_warning_exception,
)
from substitute.shared.qt_thumbnail_codec import image_from_qt_thumbnail_payload

type MediaWallPixmapCacheKey = tuple[str, int, int, int, float]
_LOGGER = get_logger("presentation.widgets.media_wall.thumbnail_cache")


class MediaWallThumbnailCache:
    """Store GUI-thread thumbnails and read already-local assets on cache misses."""

    _DEFAULT_MAXIMUM_BYTES = 128 * 1024 * 1024

    def __init__(
        self,
        *,
        asset_repository: ThumbnailAssetRepository | None = None,
        maximum_bytes: int = _DEFAULT_MAXIMUM_BYTES,
    ) -> None:
        """Initialize the cache with an optional durable thumbnail reader."""

        self._asset_repository = asset_repository
        self._maximum_bytes = max(0, maximum_bytes)
        self._cached_bytes = 0
        self._generation = 0
        self._failed_storage_keys: set[str] = set()
        self._pixmaps: OrderedDict[MediaWallPixmapCacheKey, _CachedPixmap] = (
            OrderedDict()
        )

    @property
    def generation(self) -> int:
        """Return the cache generation used to reject stale preload results."""

        return self._generation

    def pixmap_for_variants(
        self,
        variants: tuple[ThumbnailVariantReference, ...],
        size: QSize,
        *,
        device_pixel_ratio: float = 1.0,
    ) -> QPixmap | None:
        """Return a prepared scaled pixmap when it is already cached."""

        cache_key = self.cache_key_for_variants(
            variants,
            size,
            device_pixel_ratio=device_pixel_ratio,
        )
        if cache_key is None:
            return None
        variant = self.variant_for_cache_request(variants, size)
        pixmap = self.pixmap_for_cache_key(cache_key)
        if pixmap is None and variant is not None:
            pixmap = self._read_through_pixmap_for_cache_miss(
                cache_key=cache_key,
                variant=variant,
                size=size,
                device_pixel_ratio=device_pixel_ratio,
            )
        return pixmap

    def pixmap_for_cache_key(
        self, cache_key: MediaWallPixmapCacheKey
    ) -> QPixmap | None:
        """Return one cached pixmap by exact key."""

        cached = self._pixmaps.get(cache_key)
        if cached is None:
            return None
        self._pixmaps.move_to_end(cache_key)
        return cached.pixmap

    def has_pixmap(self, cache_key: MediaWallPixmapCacheKey) -> bool:
        """Return whether one exact cache key already has a pixmap."""

        return cache_key in self._pixmaps

    def pixmap_for_role(
        self,
        variants: tuple[ThumbnailVariantReference, ...],
        role: str,
        size: QSize,
        *,
        device_pixel_ratio: float = 1.0,
    ) -> QPixmap | None:
        """Return a scaled pixmap for the best available variant with one role."""

        role_variants = tuple(variant for variant in variants if variant.role == role)
        return self.pixmap_for_variants(
            role_variants,
            size,
            device_pixel_ratio=device_pixel_ratio,
        )

    def cache_key_for_variants(
        self,
        variants: tuple[ThumbnailVariantReference, ...],
        size: QSize,
        *,
        device_pixel_ratio: float = 1.0,
    ) -> MediaWallPixmapCacheKey | None:
        """Return the cache key for the best thumbnail variant and target size."""

        if not variants or size.width() <= 0 or size.height() <= 0:
            return None
        variant = self.variant_for_cache_request(variants, size)
        if variant is None:
            return None
        return (
            variant.storage_key,
            size.width(),
            size.height(),
            variant.byte_size,
            device_pixel_ratio,
        )

    def variant_for_cache_request(
        self,
        variants: tuple[ThumbnailVariantReference, ...],
        size: QSize,
    ) -> ThumbnailVariantReference | None:
        """Return the variant used by a cache or preload request."""

        if not variants or size.width() <= 0 or size.height() <= 0:
            return None
        return _best_variant(variants, max(size.width(), size.height()))

    def role_variants(
        self,
        variants: tuple[ThumbnailVariantReference, ...],
        role: str,
    ) -> tuple[ThumbnailVariantReference, ...]:
        """Return only thumbnail variants matching the requested role."""

        return tuple(variant for variant in variants if variant.role == role)

    def install_ready_image(
        self,
        *,
        cache_key: MediaWallPixmapCacheKey,
        image: QImage,
        device_pixel_ratio: float,
        generation: int,
    ) -> bool:
        """Install one prepared image as a GUI-thread pixmap."""

        if generation != self._generation:
            return False
        pixmap = QPixmap.fromImage(image)
        if pixmap.isNull():
            return False
        pixmap.setDevicePixelRatio(device_pixel_ratio)
        self._store_pixmap(cache_key, pixmap)
        return True

    def clear(self) -> None:
        """Drop cached pixmaps and invalidate in-flight preload results."""

        self._generation += 1
        self._pixmaps.clear()
        self._failed_storage_keys.clear()
        self._cached_bytes = 0

    def _read_through_pixmap_for_cache_miss(
        self,
        *,
        cache_key: MediaWallPixmapCacheKey,
        variant: ThumbnailVariantReference,
        size: QSize,
        device_pixel_ratio: float,
    ) -> QPixmap | None:
        """Synchronously install an already-local asset when first requested."""

        asset_repository = self._asset_repository
        if asset_repository is None or variant.storage_key in self._failed_storage_keys:
            return None
        try:
            asset = asset_repository.read_thumbnail_asset(variant.storage_key)
        except Exception as error:
            self._failed_storage_keys.add(variant.storage_key)
            log_warning_exception(
                _LOGGER,
                "Media wall thumbnail read-through failed",
                error=error,
                storage_key=variant.storage_key,
            )
            return None
        if asset is None:
            return None
        image = image_from_qt_thumbnail_payload(
            width=asset.width,
            height=asset.height,
            qt_format=asset.qt_format,
            bytes_per_line=asset.bytes_per_line,
            payload=asset.payload,
        )
        if image is None:
            self._failed_storage_keys.add(variant.storage_key)
            return None
        installed = self.install_ready_image(
            cache_key=cache_key,
            image=_cover_scaled_image(
                image,
                _device_pixel_size(size, device_pixel_ratio),
            ),
            device_pixel_ratio=device_pixel_ratio,
            generation=self._generation,
        )
        if not installed:
            self._failed_storage_keys.add(variant.storage_key)
            return None
        return self.pixmap_for_cache_key(cache_key)

    def _store_pixmap(
        self,
        cache_key: MediaWallPixmapCacheKey,
        pixmap: QPixmap,
    ) -> None:
        """Store one pixmap and evict least-recently-used entries over budget."""

        byte_size = _estimated_pixmap_bytes(pixmap)
        previous = self._pixmaps.pop(cache_key, None)
        if previous is not None:
            self._cached_bytes -= previous.byte_size
        if self._maximum_bytes <= 0 or byte_size > self._maximum_bytes:
            self._cached_bytes = max(0, self._cached_bytes)
            self._evict_over_budget()
            return
        self._pixmaps[cache_key] = _CachedPixmap(pixmap=pixmap, byte_size=byte_size)
        self._cached_bytes += byte_size
        self._evict_over_budget()

    def _evict_over_budget(self) -> None:
        """Evict stale pixmaps until the cache is under its byte budget."""

        while self._cached_bytes > self._maximum_bytes and self._pixmaps:
            _key, cached = self._pixmaps.popitem(last=False)
            self._cached_bytes -= cached.byte_size
        self._cached_bytes = max(0, self._cached_bytes)


@dataclass(frozen=True, slots=True)
class _CachedPixmap:
    """Track one cached pixmap and its approximate memory footprint."""

    pixmap: QPixmap
    byte_size: int


def _estimated_pixmap_bytes(pixmap: QPixmap) -> int:
    """Return a conservative byte estimate for one scaled pixmap."""

    return max(0, pixmap.width()) * max(0, pixmap.height()) * 4


def _device_pixel_size(size: QSize, device_pixel_ratio: float) -> QSize:
    """Return the positive physical pixel size for one logical thumbnail."""

    return QSize(
        max(1, round(size.width() * device_pixel_ratio)),
        max(1, round(size.height() * device_pixel_ratio)),
    )


def _cover_scaled_image(image: QImage, target_size: QSize) -> QImage:
    """Return an exact-size image produced with proportional cover scaling."""

    scaled = image.scaled(
        target_size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    left = max(0, (scaled.width() - target_size.width()) // 2)
    top = max(0, (scaled.height() - target_size.height()) // 2)
    return scaled.copy(left, top, target_size.width(), target_size.height())


def _best_variant(
    variants: tuple[ThumbnailVariantReference, ...],
    target_size: int,
) -> ThumbnailVariantReference:
    """Return the smallest variant at least as large as the requested size."""

    sorted_variants = sorted(variants, key=lambda variant: variant.size)
    for variant in sorted_variants:
        if variant.size >= target_size:
            return variant
    return sorted_variants[-1]


__all__ = ["MediaWallPixmapCacheKey", "MediaWallThumbnailCache"]

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

"""Cache prepared LoRA thumbnail pixmaps for prompt projection rendering."""

from __future__ import annotations

from collections import OrderedDict

from PySide6.QtCore import QObject, QSize, Qt, Signal
from PySide6.QtGui import QImage, QPixmap

from substitute.application.model_metadata import (
    BANNER_THUMBNAIL_ROLE,
    ThumbnailAssetRepository,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_warning_exception,
)
from substitute.shared.qt_thumbnail_codec import image_from_qt_thumbnail_payload

from .projection.model import PromptProjectionThumbnailVariant

type PromptLoraPixmapCacheKey = tuple[str, int, int, int, float]

_MAX_PIXMAP_CACHE_ENTRIES = 128
_LOGGER = get_logger("presentation.editor.prompt_editor.lora_thumbnail_cache")


class PromptLoraThumbnailCache(QObject):
    """Store GUI-thread LoRA thumbnail pixmaps behind explicit cache keys."""

    pixmap_ready = Signal(str)

    def __init__(
        self,
        asset_repository: ThumbnailAssetRepository | None = None,
    ) -> None:
        """Initialize an empty read-only pixmap cache."""

        super().__init__()
        self._asset_repository = asset_repository
        self._pixmaps: OrderedDict[PromptLoraPixmapCacheKey, QPixmap] = OrderedDict()
        self._failed_storage_keys: set[str] = set()
        self._generation = 0

    @property
    def asset_repository(self) -> ThumbnailAssetRepository | None:
        """Return the asset repository used by thumbnail preloaders."""

        return self._asset_repository

    @property
    def generation(self) -> int:
        """Return the cache generation used to reject stale preload results."""

        return self._generation

    def pixmap_for_variants(
        self,
        variants: tuple[PromptProjectionThumbnailVariant, ...],
        size: QSize,
        *,
        device_pixel_ratio: float = 1.0,
    ) -> QPixmap | None:
        """Return a cached scaled thumbnail pixmap when already available."""

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

    def banner_pixmap_for_variants(
        self,
        variants: tuple[PromptProjectionThumbnailVariant, ...],
        size: QSize,
        *,
        device_pixel_ratio: float = 1.0,
    ) -> QPixmap | None:
        """Return a cached banner pixmap when already available."""

        return self.pixmap_for_variants(
            self.banner_variants(variants),
            size,
            device_pixel_ratio=device_pixel_ratio,
        )

    def pixmap_for_cache_key(
        self,
        cache_key: PromptLoraPixmapCacheKey,
    ) -> QPixmap | None:
        """Return one cached pixmap by exact key."""

        cached = self._pixmaps.get(cache_key)
        if cached is None:
            return None
        self._pixmaps.move_to_end(cache_key)
        return cached

    def has_pixmap(self, cache_key: PromptLoraPixmapCacheKey) -> bool:
        """Return whether one exact cache key already has a pixmap."""

        return cache_key in self._pixmaps

    def cache_key_for_variants(
        self,
        variants: tuple[PromptProjectionThumbnailVariant, ...],
        size: QSize,
        *,
        device_pixel_ratio: float = 1.0,
    ) -> PromptLoraPixmapCacheKey | None:
        """Return the cache key for the best thumbnail variant and target size."""

        if not variants or size.width() <= 0 or size.height() <= 0:
            return None
        variant = self.best_variant(variants, max(size.width(), size.height()))
        return (
            variant.storage_key,
            size.width(),
            size.height(),
            variant.byte_size,
            device_pixel_ratio,
        )

    def variant_for_cache_request(
        self,
        variants: tuple[PromptProjectionThumbnailVariant, ...],
        size: QSize,
    ) -> PromptProjectionThumbnailVariant | None:
        """Return the thumbnail variant used by a cache/preload request."""

        if not variants or size.width() <= 0 or size.height() <= 0:
            return None
        return self.best_variant(variants, max(size.width(), size.height()))

    def install_ready_image(
        self,
        *,
        cache_key: PromptLoraPixmapCacheKey,
        image: QImage,
        device_pixel_ratio: float,
        generation: int,
    ) -> bool:
        """Install one preloaded image as a GUI-thread pixmap."""

        if generation != self._generation:
            return False
        pixmap = QPixmap.fromImage(image)
        if pixmap.isNull():
            return False
        pixmap.setDevicePixelRatio(device_pixel_ratio)
        self._pixmaps[cache_key] = pixmap
        self._pixmaps.move_to_end(cache_key)
        while len(self._pixmaps) > _MAX_PIXMAP_CACHE_ENTRIES:
            self._pixmaps.popitem(last=False)
        self.pixmap_ready.emit(str(cache_key[0]))
        return True

    def clear(self) -> None:
        """Drop cached scaled pixmaps after LoRA thumbnail metadata changes."""

        self._generation += 1
        self._pixmaps.clear()
        self._failed_storage_keys.clear()

    def _read_through_pixmap_for_cache_miss(
        self,
        *,
        cache_key: PromptLoraPixmapCacheKey,
        variant: PromptProjectionThumbnailVariant,
        size: QSize,
        device_pixel_ratio: float,
    ) -> QPixmap | None:
        """Synchronously install an already-local thumbnail during first paint."""

        asset_repository = self._asset_repository
        if asset_repository is None:
            return None
        if variant.storage_key in self._failed_storage_keys:
            return None
        target_size = _device_pixel_size(size, device_pixel_ratio)
        try:
            asset = asset_repository.read_thumbnail_asset(variant.storage_key)
        except Exception as error:
            self._failed_storage_keys.add(variant.storage_key)
            log_warning_exception(
                _LOGGER,
                "LoRA thumbnail read-through failed",
                error=error,
                storage_key=variant.storage_key,
                cache_key=cache_key,
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
        scaled_image = _cover_scaled_image(image, target_size)
        installed = self.install_ready_image(
            cache_key=cache_key,
            image=scaled_image,
            device_pixel_ratio=device_pixel_ratio,
            generation=self._generation,
        )
        if not installed:
            self._failed_storage_keys.add(variant.storage_key)
            return None
        pixmap = self.pixmap_for_cache_key(cache_key)
        return pixmap

    @staticmethod
    def banner_variants(
        variants: tuple[PromptProjectionThumbnailVariant, ...],
    ) -> tuple[PromptProjectionThumbnailVariant, ...]:
        """Return only banner-role thumbnail variants."""

        return tuple(
            variant for variant in variants if variant.role == BANNER_THUMBNAIL_ROLE
        )

    @staticmethod
    def best_variant(
        variants: tuple[PromptProjectionThumbnailVariant, ...],
        target_size: int,
    ) -> PromptProjectionThumbnailVariant:
        """Return the smallest variant at least as large as the requested size."""

        sorted_variants = sorted(variants, key=lambda variant: variant.size)
        for variant in sorted_variants:
            if variant.size >= target_size:
                return variant
        return sorted_variants[-1]


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


__all__ = ["PromptLoraPixmapCacheKey", "PromptLoraThumbnailCache"]

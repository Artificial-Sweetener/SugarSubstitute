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

"""Read packaged Ultralytics visuals through the thumbnail repository port."""

from __future__ import annotations

from collections.abc import Iterable
from threading import RLock

from PySide6.QtGui import QColor, QImage, QPainter

from substitute.application.model_metadata import ThumbnailAssetRepository
from substitute.application.model_metadata.ultralytics_visual_catalog import (
    BUNDLED_ULTRALYTICS_BANNER_STORAGE_PREFIX,
    BUNDLED_ULTRALYTICS_STORAGE_PREFIX,
    bundled_ultralytics_asset_names,
)
from substitute.domain.model_metadata import ThumbnailAsset
from substitute.shared.logging.logger import get_logger, log_warning
from substitute.shared.qt_thumbnail_codec import prepare_qt_thumbnail

from .resources import ultralytics_thumbnails_rc  # noqa: F401

_LOGGER = get_logger("infrastructure.model_thumbnails.bundled_ultralytics")
_RESOURCE_PREFIX = ":/substitute/model-thumbnails/ultralytics"
_BANNER_WASH = QColor(48, 48, 48, 104)


class BundledUltralyticsThumbnailRepository:
    """Serve immutable packaged detector thumbnails by logical storage key."""

    def __init__(self) -> None:
        """Initialize an in-memory decode cache for packaged images."""

        self._asset_names = frozenset(bundled_ultralytics_asset_names())
        self._assets: dict[str, ThumbnailAsset] = {}
        self._lock = RLock()

    def read_thumbnail_asset(self, storage_key: str) -> ThumbnailAsset | None:
        """Return one packaged thumbnail, or ``None`` for unrelated keys."""

        banner_variant = storage_key.startswith(
            BUNDLED_ULTRALYTICS_BANNER_STORAGE_PREFIX
        )
        if banner_variant:
            asset_name = storage_key.removeprefix(
                BUNDLED_ULTRALYTICS_BANNER_STORAGE_PREFIX
            )
        elif storage_key.startswith(BUNDLED_ULTRALYTICS_STORAGE_PREFIX):
            asset_name = storage_key.removeprefix(BUNDLED_ULTRALYTICS_STORAGE_PREFIX)
        else:
            return None
        if asset_name not in self._asset_names:
            log_warning(
                _LOGGER,
                "Rejected unknown bundled Ultralytics thumbnail key",
                storage_key=storage_key,
            )
            return None
        with self._lock:
            cached = self._assets.get(storage_key)
            if cached is not None:
                return cached
            asset = self._load_asset(
                storage_key=storage_key,
                asset_name=asset_name,
                banner_variant=banner_variant,
            )
            if asset is not None:
                self._assets[storage_key] = asset
            return asset

    @staticmethod
    def _load_asset(
        *,
        storage_key: str,
        asset_name: str,
        banner_variant: bool,
    ) -> ThumbnailAsset | None:
        """Decode and prepare one validated Qt resource image."""

        image = QImage(f"{_RESOURCE_PREFIX}/{asset_name}.png")
        if image.isNull():
            log_warning(
                _LOGGER,
                "Bundled Ultralytics thumbnail resource is unavailable",
                storage_key=storage_key,
                asset_name=asset_name,
            )
            return None
        if banner_variant:
            painter = QPainter(image)
            painter.fillRect(image.rect(), _BANNER_WASH)
            painter.end()
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


class LayeredThumbnailAssetRepository:
    """Read thumbnail assets from ordered repositories with fallback."""

    def __init__(self, repositories: Iterable[ThumbnailAssetRepository]) -> None:
        """Store the repositories in authoritative lookup order."""

        self._repositories = tuple(repositories)

    def read_thumbnail_asset(self, storage_key: str) -> ThumbnailAsset | None:
        """Return the first asset provided for one logical storage key."""

        for repository in self._repositories:
            asset = repository.read_thumbnail_asset(storage_key)
            if asset is not None:
                return asset
        return None


__all__ = [
    "BundledUltralyticsThumbnailRepository",
    "LayeredThumbnailAssetRepository",
]

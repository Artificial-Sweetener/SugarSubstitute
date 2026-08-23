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

"""Prompt LoRA thumbnail-cache contracts."""

from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor

from substitute.domain.model_metadata import BANNER_THUMBNAIL_ROLE
from substitute.presentation.editor.prompt_editor.lora_thumbnail_cache import (
    PromptLoraThumbnailCache,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionThumbnailVariant,
)

from tests.presentation.editor.prompt_editor.lora_rendering.support import (
    _AssetRepository,
    _thumbnail_asset,
    ensure_qapp,
)


def test_lora_banner_thumbnail_cache_returns_exact_cover_size() -> None:
    """Banner cache read-through should crop cached assets to target size."""

    ensure_qapp()
    asset = _thumbnail_asset(
        "square:banner:128",
        QColor("#4068d8"),
        width=128,
        height=128,
    )
    repository = _AssetRepository({"square:banner:128": asset})
    cache = PromptLoraThumbnailCache(repository)

    variants = (
        PromptProjectionThumbnailVariant(
            size=128,
            storage_key="square:banner:128",
            width=128,
            height=128,
            content_format=asset.content_format,
            byte_size=len(asset.payload),
            role=BANNER_THUMBNAIL_ROLE,
        ),
    )
    pixmap = cache.banner_pixmap_for_variants(
        variants,
        QSize(220, 40),
        device_pixel_ratio=2.0,
    )

    assert pixmap is not None
    assert repository.reads == ["square:banner:128"]
    assert pixmap.width() == 440
    assert pixmap.height() == 80
    assert pixmap.devicePixelRatioF() == 2.0


def test_lora_banner_thumbnail_cache_uses_later_local_asset() -> None:
    """Missing cached LoRA assets should be picked up on a later cache lookup."""

    ensure_qapp()
    storage_key = "later:banner:768x160"
    asset = _thumbnail_asset(storage_key, QColor("#45b36b"))
    repository = _AssetRepository({})
    cache = PromptLoraThumbnailCache(repository)
    variants = (
        PromptProjectionThumbnailVariant(
            size=768,
            storage_key=storage_key,
            width=768,
            height=160,
            content_format=asset.content_format,
            byte_size=len(asset.payload),
            role=BANNER_THUMBNAIL_ROLE,
        ),
    )

    first_pixmap = cache.banner_pixmap_for_variants(variants, QSize(220, 40))
    repository.assets[storage_key] = asset
    second_pixmap = cache.banner_pixmap_for_variants(variants, QSize(220, 40))

    assert first_pixmap is None
    assert second_pixmap is not None
    assert repository.reads == [storage_key, storage_key]

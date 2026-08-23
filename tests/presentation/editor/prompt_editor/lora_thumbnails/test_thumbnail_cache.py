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

"""Contracts for prompt-editor LoRA thumbnail cache failure handling."""

from __future__ import annotations


from typing import cast

from PySide6.QtCore import QSize

from substitute.presentation.editor.prompt_editor.lora_thumbnail_cache import (
    PromptLoraThumbnailCache,
)
from tests.presentation.editor.prompt_editor.lora_thumbnails.support import (
    _FailingThumbnailAssetRepository,
    _InvalidThumbnailAssetRepository,
    _projection_thumbnail_variant,
)


def test_lora_thumbnail_cache_clear_drops_scaled_pixmaps() -> None:
    """LoRA metadata refresh can discard stale scaled pixmaps."""

    cache = PromptLoraThumbnailCache()
    pixmaps = cast(dict[object, object], cache._pixmaps)
    pixmaps[("storage", 16, 16, 128, 1.0)] = object()

    cache.clear()

    assert cache._pixmaps == {}


def test_lora_thumbnail_cache_handles_repository_failure() -> None:
    """Thumbnail repository failures queue asynchronously and return missing."""

    repository = _FailingThumbnailAssetRepository()
    cache = PromptLoraThumbnailCache(repository)
    variants = (_projection_thumbnail_variant("broken:banner:128"),)

    first_pixmap = cache.pixmap_for_variants(variants, QSize(32, 32))
    second_pixmap = cache.pixmap_for_variants(variants, QSize(32, 32))

    assert first_pixmap is None
    assert second_pixmap is None
    assert repository.reads <= 1


def test_lora_thumbnail_cache_handles_invalid_payload() -> None:
    """Invalid thumbnail payloads queue asynchronously and return missing."""

    repository = _InvalidThumbnailAssetRepository()
    cache = PromptLoraThumbnailCache(repository)
    variants = (_projection_thumbnail_variant("invalid:banner:128"),)

    first_pixmap = cache.pixmap_for_variants(variants, QSize(32, 32))
    second_pixmap = cache.pixmap_for_variants(variants, QSize(32, 32))

    assert first_pixmap is None
    assert second_pixmap is None
    assert repository.reads <= 1

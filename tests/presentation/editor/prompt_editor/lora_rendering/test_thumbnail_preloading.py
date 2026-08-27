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

"""Prompt LoRA thumbnail-preloading contracts."""

from __future__ import annotations

import logging

import pytest
from PySide6.QtCore import QSize
from PySide6.QtGui import QColor

from substitute.domain.model_metadata import BANNER_THUMBNAIL_ROLE
from substitute.presentation.editor.prompt_editor.lora_thumbnail_cache import (
    PromptLoraThumbnailCache,
)
from substitute.presentation.editor.prompt_editor.async_work import (
    PromptLoraThumbnailPreloader,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionThumbnailVariant,
)

from tests.presentation.editor.prompt_editor.lora_rendering.support import (
    _AssetRepository,
    _ImmediateDispatcher,
    _FailingAssetRepository,
    _immediate_prompt_executor,
    _thumbnail_asset,
    ensure_qapp,
)


def test_lora_banner_thumbnail_preloader_installs_cached_asset_immediately() -> None:
    """Startup-visible LoRA banners should hydrate from local assets synchronously."""

    ensure_qapp()
    asset = _thumbnail_asset("immediate:banner:768x160", QColor("#51a8ff"))
    repository = _AssetRepository({"immediate:banner:768x160": asset})
    cache = PromptLoraThumbnailCache(repository)
    variants = (
        PromptProjectionThumbnailVariant(
            size=768,
            storage_key="immediate:banner:768x160",
            width=768,
            height=160,
            content_format=asset.content_format,
            byte_size=len(asset.payload),
            role=BANNER_THUMBNAIL_ROLE,
        ),
    )
    preloader = PromptLoraThumbnailPreloader(
        cache=cache,
        executor=_immediate_prompt_executor(),
    )

    installed = preloader.install_banner_pixmap_for_variants_now(
        variants,
        QSize(220, 40),
        device_pixel_ratio=1.5,
    )

    assert installed is True
    assert preloader.has_pending_work() is False
    assert repository.reads == ["immediate:banner:768x160"]
    pixmap = cache.banner_pixmap_for_variants(
        variants,
        QSize(220, 40),
        device_pixel_ratio=1.5,
    )
    assert pixmap is not None
    assert pixmap.width() == 330
    assert pixmap.height() == 60
    assert pixmap.devicePixelRatioF() == 1.5


def test_lora_banner_thumbnail_cache_notifies_idle_after_gui_install() -> None:
    """Idle callbacks should run only after ready banner pixmaps are installed."""

    ensure_qapp()
    asset = _thumbnail_asset("midna:banner:768x160", QColor("#cc3355"))
    repository = _AssetRepository({"midna:banner:768x160": asset})
    cache = PromptLoraThumbnailCache()
    callbacks: list[str] = []
    variants = (
        PromptProjectionThumbnailVariant(
            size=768,
            storage_key="midna:banner:768x160",
            width=768,
            height=160,
            content_format=asset.content_format,
            byte_size=len(asset.payload),
            role=BANNER_THUMBNAIL_ROLE,
        ),
    )

    assert (
        cache.banner_pixmap_for_variants(
            variants,
            QSize(220, 40),
            device_pixel_ratio=1.0,
        )
        is None
    )
    preloader = PromptLoraThumbnailPreloader(
        cache=cache,
        asset_repository=repository,
        dispatcher=_ImmediateDispatcher(),
        executor=_immediate_prompt_executor(),
    )
    assert preloader.preload_banner_pixmap_for_variants(
        variants,
        QSize(220, 40),
        device_pixel_ratio=1.0,
    )
    preloader.run_when_idle(lambda: callbacks.append("idle"))

    assert callbacks == ["idle"]
    assert cache.banner_pixmap_for_variants(
        variants,
        QSize(220, 40),
        device_pixel_ratio=1.0,
    )


def test_lora_banner_thumbnail_preloader_failure_clears_pending_and_notifies_idle() -> (
    None
):
    """Failed thumbnail loads should clear pending state and release idle waiters."""

    ensure_qapp()
    repository = _AssetRepository({})
    cache = PromptLoraThumbnailCache(repository)
    callbacks: list[str] = []
    variants = (
        PromptProjectionThumbnailVariant(
            size=768,
            storage_key="missing:banner:768x160",
            width=768,
            height=160,
            content_format="image/png",
            byte_size=0,
            role=BANNER_THUMBNAIL_ROLE,
        ),
    )
    preloader = PromptLoraThumbnailPreloader(
        cache=cache,
        dispatcher=_ImmediateDispatcher(),
        executor=_immediate_prompt_executor(),
    )

    assert preloader.preload_banner_pixmap_for_variants(
        variants,
        QSize(220, 40),
        device_pixel_ratio=1.0,
    )
    preloader.run_when_idle(lambda: callbacks.append("idle"))

    assert callbacks == ["idle"]
    assert preloader.has_pending_work() is False
    assert not preloader.preload_banner_pixmap_for_variants(
        variants,
        QSize(220, 40),
        device_pixel_ratio=1.0,
    )
    assert repository.reads == ["missing:banner:768x160"]


def test_lora_banner_thumbnail_preloader_exception_log_is_prompt_safe(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Thumbnail preload exceptions should preserve traceback without source text."""

    ensure_qapp()
    repository = _FailingAssetRepository({})
    cache = PromptLoraThumbnailCache(repository)
    callbacks: list[str] = []
    variants = (
        PromptProjectionThumbnailVariant(
            size=768,
            storage_key="failing:banner:768x160",
            width=768,
            height=160,
            content_format="image/png",
            byte_size=0,
            role=BANNER_THUMBNAIL_ROLE,
        ),
    )
    preloader = PromptLoraThumbnailPreloader(
        cache=cache,
        dispatcher=_ImmediateDispatcher(),
        executor=_immediate_prompt_executor(),
    )
    caplog.set_level(logging.WARNING)

    assert preloader.preload_banner_pixmap_for_variants(
        variants,
        QSize(220, 40),
        device_pixel_ratio=1.0,
    )
    preloader.run_when_idle(lambda: callbacks.append("idle"))

    assert callbacks == ["idle"]
    assert preloader.has_pending_work() is False
    assert "LoRA thumbnail asset load failed" in caplog.text
    assert "error_type=RuntimeError" in caplog.text
    assert "prompt thumbnail secret" not in caplog.text

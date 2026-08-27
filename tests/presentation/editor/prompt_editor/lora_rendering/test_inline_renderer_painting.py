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

"""Prompt LoRA inline-renderer paint-state contracts."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize
from PySide6.QtGui import QColor, QFont, QImage, QPainter

from substitute.application.prompt_editor.lora.resolution import (
    PromptLoraResolutionStatus,
)
from substitute.domain.model_metadata import BANNER_THUMBNAIL_ROLE
from substitute.presentation.editor.prompt_editor.lora_thumbnail_cache import (
    PromptLoraThumbnailCache,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionThumbnailVariant,
)
from substitute.presentation.editor.prompt_editor.projection.tokens import (
    PromptLoraInlineObjectRenderer,
)
from substitute.presentation.semantic_colors import semantic_error_color

from tests.presentation.editor.prompt_editor.lora_rendering.support import (
    _AssetRepository,
    _run,
    _thumbnail_asset,
    _token,
    ensure_qapp,
)


def test_lora_renderer_reads_local_banner_asset_when_painting() -> None:
    """Painting should hydrate already-local banner assets on first lookup."""

    app = ensure_qapp()
    asset = _thumbnail_asset("midna:banner:768x160", QColor("#cc3355"))
    repository = _AssetRepository({"midna:banner:768x160": asset})
    cache = PromptLoraThumbnailCache(repository)
    renderer = PromptLoraInlineObjectRenderer(cache)
    target = QImage(220, 40, QImage.Format.Format_ARGB32_Premultiplied)
    target.fill(QColor("#00000000"))
    painter = QPainter(target)

    renderer.paint_inline_object(
        painter,
        QRectF(4.0, 4.0, 200.0, 26.0),
        _run("Mineru"),
        _token(
            thumbnail_variants=(
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
        ),
        base_font=QFont(),
        palette=app.palette(),
    )
    painter.end()

    assert repository.reads == ["midna:banner:768x160"]
    assert target.pixelColor(100, 16).alpha() > 0


def test_lora_renderer_paints_cached_banner_while_resolution_is_pending() -> None:
    """Known thumbnails should decorate LoRA chips before catalog authority catches up."""

    app = ensure_qapp()
    asset = _thumbnail_asset("midna:banner:768x160", QColor("#cc3355"))
    cache = PromptLoraThumbnailCache()
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
    cache_key = cache.cache_key_for_variants(
        variants,
        QSize(200, 26),
        device_pixel_ratio=1.0,
    )
    assert cache_key is not None
    ready_image = QImage(200, 26, QImage.Format.Format_ARGB32_Premultiplied)
    ready_image.fill(QColor("#cc3355"))
    assert cache.install_ready_image(
        cache_key=cache_key,
        image=ready_image,
        device_pixel_ratio=1.0,
        generation=cache.generation,
    )
    renderer = PromptLoraInlineObjectRenderer(cache)
    target = QImage(220, 40, QImage.Format.Format_ARGB32_Premultiplied)
    target.fill(QColor("#00000000"))
    painter = QPainter(target)

    renderer.paint_inline_object(
        painter,
        QRectF(4.0, 4.0, 200.0, 26.0),
        _run("Mineru"),
        _token(
            thumbnail_variants=variants,
            lora_status=PromptLoraResolutionStatus.PENDING_NO_AUTHORITY,
        ),
        base_font=QFont(),
        palette=app.palette(),
    )
    painter.end()

    assert target.pixelColor(100, 16).alpha() > 0


def test_lora_renderer_suppressed_banners_do_not_request_thumbnail_assets() -> None:
    """Suppressed banner mode should paint fallback chrome without thumbnail reads."""

    app = ensure_qapp()
    asset = _thumbnail_asset("midna:banner:768x160", QColor("#cc3355"))
    repository = _AssetRepository({"midna:banner:768x160": asset})
    renderer = PromptLoraInlineObjectRenderer(
        PromptLoraThumbnailCache(repository),
        suppress_banners=True,
    )
    target = QImage(220, 40, QImage.Format.Format_ARGB32_Premultiplied)
    target.fill(QColor("#00000000"))
    painter = QPainter(target)

    renderer.paint_inline_object(
        painter,
        QRectF(4.0, 4.0, 200.0, 26.0),
        _run("Mineru"),
        _token(
            thumbnail_variants=(
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
        ),
        base_font=QFont(),
        palette=app.palette(),
    )
    painter.end()

    assert repository.reads == []
    assert target.pixelColor(100, 16).alpha() > 0


def test_lora_renderer_suppressed_banners_keep_normal_measurement() -> None:
    """Suppressed banner mode should not alter LoRA chip layout geometry."""

    ensure_qapp()
    token = _token(
        thumbnail_variants=(
            PromptProjectionThumbnailVariant(
                size=768,
                storage_key="midna:banner:768x160",
                width=768,
                height=160,
                content_format="png",
                byte_size=1024,
                role=BANNER_THUMBNAIL_ROLE,
            ),
        )
    )
    run = _run("Mineru")
    font = QFont()

    normal_size = PromptLoraInlineObjectRenderer().measure_inline_object(
        run,
        token,
        base_font=font,
    )
    suppressed_size = PromptLoraInlineObjectRenderer(
        suppress_banners=True
    ).measure_inline_object(
        run,
        token,
        base_font=font,
    )

    assert suppressed_size == normal_size


def test_lora_renderer_uses_error_accent_for_missing_lora() -> None:
    """Missing LoRA chips should use the semantic error color."""

    ensure_qapp()
    renderer = PromptLoraInlineObjectRenderer()
    _fill, _border, accent = renderer._colors_for_token(  # noqa: SLF001
        _token(exists=False)
    )
    expected = semantic_error_color()

    assert (accent.red(), accent.green(), accent.blue()) == (
        expected.red(),
        expected.green(),
        expected.blue(),
    )


def test_lora_renderer_missing_lora_reads_local_banner_asset() -> None:
    """Missing LoRA chips should still use already-local banner assets."""

    app = ensure_qapp()
    asset = _thumbnail_asset("midna:banner:768x160", QColor("#cc3355"))
    repository = _AssetRepository({"midna:banner:768x160": asset})
    renderer = PromptLoraInlineObjectRenderer(
        PromptLoraThumbnailCache(repository),
    )
    target = QImage(220, 40, QImage.Format.Format_ARGB32_Premultiplied)
    target.fill(QColor("#00000000"))
    painter = QPainter(target)

    renderer.paint_inline_object(
        painter,
        QRectF(4.0, 4.0, 200.0, 26.0),
        _run("Missing"),
        _token(
            exists=False,
            thumbnail_variants=(
                PromptProjectionThumbnailVariant(
                    size=768,
                    storage_key="midna:banner:768x160",
                    width=768,
                    height=160,
                    content_format=asset.content_format,
                    byte_size=len(asset.payload),
                    role=BANNER_THUMBNAIL_ROLE,
                ),
            ),
        ),
        base_font=QFont(),
        palette=app.palette(),
    )
    painter.end()

    assert repository.reads == ["midna:banner:768x160"]
    assert target.pixelColor(100, 16).alpha() > 0

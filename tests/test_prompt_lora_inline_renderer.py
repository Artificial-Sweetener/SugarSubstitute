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

"""Tests for LoRA inline chevron renderer behavior."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import cast

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF, QSize
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter
from PySide6.QtWidgets import QApplication

from substitute.application.prompt_editor.prompt_lora_resolution_service import (
    PromptLoraResolutionStatus,
)
from tests.execution_testing import ImmediateTaskSubmitter
from substitute.domain.model_metadata import BANNER_THUMBNAIL_ROLE, ThumbnailAsset
from substitute.presentation.editor.prompt_editor.lora_thumbnail_cache import (
    PromptLoraThumbnailCache,
)
from substitute.presentation.editor.prompt_editor.async_work import (
    PromptEditorTaskExecutor,
    PromptLoraThumbnailPreloader,
)
from substitute.presentation.editor.prompt_editor.projection.model import (
    PromptProjectionRun,
    PromptProjectionRunKind,
    PromptProjectionThumbnailVariant,
    PromptProjectionToken,
    PromptProjectionTokenKind,
)
from substitute.presentation.editor.prompt_editor.projection.metrics import (
    projection_text_line_height,
)
from substitute.presentation.editor.prompt_editor.projection.tokens import (
    PromptLoraInlineObjectRenderer,
)
from substitute.presentation.semantic_colors import semantic_error_color
from substitute.shared.qt_thumbnail_codec import prepare_qt_thumbnail


class _ImmediateDispatcher:
    """Publish test callbacks synchronously."""

    def publish(self, callback: Callable[[], None], *, reason: str) -> None:
        """Run one callback immediately."""

        _ = reason
        callback()


def _immediate_prompt_executor() -> PromptEditorTaskExecutor:
    """Return an immediate prompt task executor for thumbnail tests."""

    return PromptEditorTaskExecutor(
        submitter=ImmediateTaskSubmitter(),
        shutdown_callback=lambda: None,
    )


class _AssetRepository:
    """Return configured thumbnail assets and record storage-key reads."""

    def __init__(self, assets: dict[str, ThumbnailAsset]) -> None:
        """Store assets keyed by thumbnail storage key."""

        self.assets = assets
        self.reads: list[str] = []

    def read_thumbnail_asset(self, storage_key: str) -> ThumbnailAsset | None:
        """Return one asset while recording the storage key."""

        self.reads.append(storage_key)
        return self.assets.get(storage_key)


class _FailingAssetRepository(_AssetRepository):
    """Raise a prompt-like message while recording storage-key reads."""

    def __init__(self, assets: dict[str, ThumbnailAsset]) -> None:
        """Store assets and one prompt-like dynamic exception message."""

        super().__init__(assets)
        self.error_message = "prompt thumbnail secret"

    def read_thumbnail_asset(self, storage_key: str) -> ThumbnailAsset | None:
        """Raise a deterministic repository failure."""

        self.reads.append(storage_key)
        raise RuntimeError(self.error_message)


def ensure_qapp() -> QApplication:
    """Return a running Qt application for renderer tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def test_lora_renderer_measures_content_width_with_long_title_cap() -> None:
    """LoRA bars should stay shorter than the canonical projection row height."""

    ensure_qapp()
    renderer = PromptLoraInlineObjectRenderer()
    run = _run("fizrot (artist style) [Illustrious]")
    token = _token()
    font = QFont()

    size = renderer.measure_inline_object(run, token, base_font=font)

    assert 120 <= size.width() <= 360
    assert size.height() < projection_text_line_height(font)


def test_lora_renderer_keeps_weight_rect_inside_canonical_height() -> None:
    """LoRA weight chrome should not protrude beyond the measured chip height."""

    ensure_qapp()
    renderer = PromptLoraInlineObjectRenderer()
    run = _run("Mineru")
    token = _token()
    font = QFont()
    size = renderer.measure_inline_object(run, token, base_font=font)

    weight_rect = renderer.weight_text_rect(
        run,
        token,
        QRectF(0.0, 0.0, size.width(), size.height()),
        base_font=font,
    )

    assert weight_rect is not None
    assert weight_rect.height() <= size.height()
    assert weight_rect.top() >= 0.0
    assert weight_rect.bottom() <= size.height()


def test_lora_renderer_uses_smaller_title_font() -> None:
    """LoRA page and version labels should be slightly smaller than editor text."""

    ensure_qapp()
    renderer = PromptLoraInlineObjectRenderer()
    base_font = QFont()
    title_font = renderer._title_font(base_font)  # noqa: SLF001

    assert QFontMetricsF(title_font).height() <= QFontMetricsF(base_font).height()
    assert QFontMetricsF(title_font).horizontalAdvance("Mineru") < QFontMetricsF(
        base_font
    ).horizontalAdvance("Mineru")


def test_lora_renderer_caps_page_and_version_character_counts() -> None:
    """LoRA labels should be character-capped before width-based elision."""

    ensure_qapp()
    renderer = PromptLoraInlineObjectRenderer()
    metrics = QFontMetricsF(QFont())

    segments = renderer._title_segments(  # noqa: SLF001
        metrics,
        page_text="Extremely Long CivitAI Collection Page Name With Extra Words",
        version_text="Overly Detailed Version Name With Extra Words",
        available_width=600.0,
    )

    assert segments == (
        "Extremely Long Ci...",
        " - ",
        "Overly Detai...",
    )
    assert len(segments[0]) == 20
    assert len(segments[2]) == 15


def test_lora_renderer_weight_changes_do_not_shift_normal_bar_width() -> None:
    """Common LoRA weight edits should use a stable reserved weight slot."""

    ensure_qapp()
    renderer = PromptLoraInlineObjectRenderer()
    run = _run("Mineru")
    font = QFont()

    widths = {
        renderer.measure_inline_object(
            run,
            _token(value_text=value_text),
            base_font=font,
        ).width()
        for value_text in ("0.80", "1.00", "1.25", "-0.25")
    }

    assert len(widths) == 1


def test_lora_renderer_keeps_version_visible_after_page_elision() -> None:
    """Long page names should elide before the LoRA version label disappears."""

    ensure_qapp()
    renderer = PromptLoraInlineObjectRenderer()
    metrics = QFontMetricsF(QFont())

    segments = renderer._title_segments(  # noqa: SLF001
        metrics,
        page_text="Extremely Long CivitAI Collection Page Name With Extra Words",
        version_text="Battoujutsu Variant",
        available_width=145.0,
    )

    assert len(segments) == 3
    assert segments[1] == " - "
    assert segments[0] != "Extremely Long CivitAI Collection Page Name With Extra Words"
    assert segments[2]


def test_lora_renderer_exact_edit_uses_existing_pill_width_without_growth() -> None:
    """Exact edit mode should not add LoRA weight padding twice."""

    ensure_qapp()
    renderer = PromptLoraInlineObjectRenderer()
    run = _run("Mineru")
    font = QFont()
    normal_token = _token(value_text="0.80")

    normal_size = renderer.measure_inline_object(run, normal_token, base_font=font)
    normal_weight_rect = renderer.weight_text_rect(
        run,
        normal_token,
        QRectF(0.0, 0.0, normal_size.width(), normal_size.height()),
        base_font=font,
    )
    assert normal_weight_rect is not None
    editing_size = renderer.measure_inline_object(
        run,
        _token(
            value_text="0.80",
            editing_value_text="0.80",
            editing_slot_width=normal_weight_rect.width(),
        ),
        base_font=font,
    )

    assert editing_size == normal_size


def test_lora_renderer_chevron_path_has_sharp_angle_ends() -> None:
    """The rendered LoRA bar shape should use sharp angle-bracket tips."""

    ensure_qapp()
    renderer = PromptLoraInlineObjectRenderer()
    path = renderer._chevron_path(QRectF(0.0, 0.0, 120.0, 24.0))  # noqa: SLF001

    polygon = path.toFillPolygon()
    first = polygon.at(0)
    second = polygon.at(1)
    fourth = polygon.at(3)

    assert first.x() == 0
    assert first.y() == 12
    assert second.x() > 0
    assert second.y() == 0
    assert fourth.x() == 120
    assert fourth.y() == 12


def test_lora_renderer_keeps_weight_rect_available_for_controls() -> None:
    """Existing weight controls should still have a stable weight slot."""

    ensure_qapp()
    renderer = PromptLoraInlineObjectRenderer()
    run = _run("Mineru")
    token = _token()
    rect = QRectF(0.0, 0.0, 180.0, 26.0)

    weight_rect = renderer.weight_text_rect(run, token, rect, base_font=QFont())
    anchor_rect = renderer.anchor_rect(run, token, rect, base_font=QFont())

    assert weight_rect is not None
    assert anchor_rect is not None
    assert weight_rect == anchor_rect
    assert weight_rect.right() < rect.right()
    assert weight_rect.left() > rect.center().x()


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


def _run(display_text: str) -> PromptProjectionRun:
    """Return one inline-object LoRA projection run."""

    return PromptProjectionRun(
        run_id="run:lora",
        kind=PromptProjectionRunKind.INLINE_OBJECT,
        source_start=0,
        source_end=20,
        display_text=display_text,
        source_positions=(0, 20),
        projection_start=0,
        projection_end=1,
        token_id="lora:0",
        renderer_key="lora_chip",
    )


def _token(
    *,
    thumbnail_variants: tuple[PromptProjectionThumbnailVariant, ...] = (),
    value_text: str = "0.8",
    editing_value_text: str | None = None,
    editing_slot_width: float | None = None,
    lora_version_text: str | None = None,
    exists: bool = True,
    lora_status: PromptLoraResolutionStatus | None = None,
) -> PromptProjectionToken:
    """Return one LoRA projection token."""

    resolved_lora_status = lora_status or (
        PromptLoraResolutionStatus.FOUND
        if exists
        else PromptLoraResolutionStatus.MISSING
    )
    return PromptProjectionToken(
        token_id="lora:0",
        kind=PromptProjectionTokenKind.LORA,
        source_start=0,
        source_end=20,
        display_text="Mineru",
        value_text=value_text,
        lora_version_text=lora_version_text,
        exists=exists,
        lora_status=resolved_lora_status,
        editing_value_text=editing_value_text,
        editing_slot_width=editing_slot_width,
        thumbnail_variants=thumbnail_variants,
    )


def _thumbnail_asset(
    storage_key: str,
    color: QColor,
    *,
    width: int = 768,
    height: int = 160,
) -> ThumbnailAsset:
    """Return one Qt-ready banner thumbnail asset."""

    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(color)
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

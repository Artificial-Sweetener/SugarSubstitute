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

"""Tests for reusable combo banner decoration painting."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtCore import QRect, QRectF, QSize
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import QApplication, QWidget

from substitute.domain.model_metadata import (
    BANNER_THUMBNAIL_ROLE,
    STANDARD_THUMBNAIL_ROLE,
)
from substitute.presentation.widgets.combo_banner_decoration import (
    ComboBannerDecoration,
    ComboBannerDisplay,
)
from substitute.presentation.widgets.media_wall import (
    MediaWallThumbnailCache,
    ThumbnailVariantReference,
)
from tests.support.qt.lifecycle import destroy_qt_object


@pytest.fixture
def banner_paint_widget() -> Iterator[QWidget]:
    """Yield a painting widget and synchronously release its Qt resources."""

    widget = QWidget()
    try:
        yield widget
    finally:
        destroy_qt_object(widget)


def test_combo_banner_decoration_paints_banner_role(
    qt_application_owner: QApplication,
    banner_paint_widget: QWidget,
) -> None:
    """Closed combo decoration should paint banner artwork and text."""

    cache = _cache_with_ready_banner("banner", QColor("#2868d8"))
    decoration = ComboBannerDecoration(thumbnail_cache=cache)
    variants = (
        _variant("standard", role=STANDARD_THUMBNAIL_ROLE),
        _variant("banner", role=BANNER_THUMBNAIL_ROLE),
    )
    target = _blank_image()
    painter = QPainter(target)

    try:
        painted = decoration.paint_closed_display(
            painter,
            banner_paint_widget,
            display=_display(variants=variants),
            rect=QRect(0, 0, 220, 34),
            text_rect=QRect(11, 0, 178, 34),
            chevron_rect=None,
            palette=qt_application_owner.palette(),
            font=QFont(),
            border_radius=5.0,
        )
    finally:
        painter.end()

    assert painted is True
    assert target.pixelColor(205, 17).alpha() > 0
    assert target.pixelColor(205, 17).blue() > 120


def test_combo_banner_decoration_noops_without_banner_when_fallback_disabled(
    qt_application_owner: QApplication,
    banner_paint_widget: QWidget,
) -> None:
    """Missing banner artwork should leave native combo painting untouched."""

    decoration = ComboBannerDecoration(thumbnail_cache=MediaWallThumbnailCache())
    target = _blank_image()
    before = target.copy()
    painter = QPainter(target)

    try:
        painted = decoration.paint_closed_display(
            painter,
            banner_paint_widget,
            display=_display(
                variants=(_variant("standard", role=STANDARD_THUMBNAIL_ROLE),)
            ),
            rect=QRect(0, 0, 220, 34),
            text_rect=QRect(11, 0, 178, 34),
            chevron_rect=None,
            palette=qt_application_owner.palette(),
            font=QFont(),
            border_radius=5.0,
        )
    finally:
        painter.end()

    assert painted is False
    assert target == before


def test_combo_banner_decoration_paints_shadowed_chevron(
    qt_application_owner: QApplication,
    banner_paint_widget: QWidget,
) -> None:
    """Closed banner combo decoration should shadow the drop chevron too."""

    cache = _cache_with_ready_banner("banner", QColor("#ffffff"))
    decoration = ComboBannerDecoration(thumbnail_cache=cache)
    target = _blank_image()
    painter = QPainter(target)

    try:
        painted = decoration.paint_closed_display(
            painter,
            banner_paint_widget,
            display=_display(
                variants=(_variant("banner", role=BANNER_THUMBNAIL_ROLE),)
            ),
            rect=QRect(0, 0, 220, 34),
            text_rect=QRect(11, 0, 160, 34),
            chevron_rect=QRectF(190.0, 12.0, 10.0, 10.0),
            palette=qt_application_owner.palette(),
            font=QFont(),
            border_radius=5.0,
        )
    finally:
        painter.end()

    untouched_banner_pixel = target.pixelColor(205, 17).lightness()
    shadow_pixel = target.pixelColor(196, 19).lightness()

    assert painted is True
    assert target.pixelColor(195, 18).lightness() > untouched_banner_pixel
    assert shadow_pixel < untouched_banner_pixel


def _display(
    *,
    variants: tuple[ThumbnailVariantReference, ...],
) -> ComboBannerDisplay:
    """Return one combo decoration display model."""

    return ComboBannerDisplay(
        title="A Very Long Model Name That Should Elide",
        subtitle="v12",
        banner_variants=variants,
        fallback_key="model",
        tooltip="A Very Long Model Name That Should Elide - v12",
    )


def _variant(storage_key: str, *, role: str) -> ThumbnailVariantReference:
    """Return one prepared thumbnail reference."""

    return ThumbnailVariantReference(
        storage_key=storage_key,
        size=768,
        width=768,
        height=160,
        content_format="sqthumb-qimage-argb32-premultiplied",
        byte_size=768 * 160 * 4,
        role=role,
    )


def _cache_with_ready_banner(
    storage_key: str, color: QColor
) -> MediaWallThumbnailCache:
    """Return a cache with one prepared banner pixmap installed."""

    cache = MediaWallThumbnailCache()
    variants = (_variant(storage_key, role=BANNER_THUMBNAIL_ROLE),)
    cache_key = cache.cache_key_for_variants(variants, QSize(220, 34))
    assert cache_key is not None
    image = QImage(220, 34, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(color)
    assert cache.install_ready_image(
        cache_key=cache_key,
        image=image,
        device_pixel_ratio=1.0,
        generation=cache.generation,
    )
    return cache


def _blank_image() -> QImage:
    """Return a transparent target image."""

    image = QImage(220, 34, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#00000000"))
    return image
